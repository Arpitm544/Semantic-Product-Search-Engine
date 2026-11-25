"""See what the running backend is doing: request IDs, JSON logs and live metrics.

Everything is kept in memory with fixed limits, so memory never grows:
- counters are a few numbers;
- request and search timings keep only the latest WINDOW entries;
- searches that found nothing good keep only the latest ZERO_KEEP texts
  (no user IDs). "Nothing good" means no results, or no result the careful
  check (cross-encoder) estimates to be at least 20% likely to be relevant.
Numbers start again from zero when the server restarts.

Request logs are written as JSON to standard output and omit search text and
query strings. The local launcher also disables Uvicorn's access log.
"""
from collections import Counter, defaultdict, deque
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps
import json
import logging
import os
import re
import sys
from threading import Lock
from time import perf_counter, time
from uuid import uuid4

from src.search.relevance import RELEVANCE_THRESHOLD
from src.evaluation.metrics import percentile

WINDOW = 1000          # latest searches whose step timings are kept
ROUTE_WINDOW = 200     # latest timings kept per API route
ZERO_KEEP = 500        # latest zero-result search texts kept
QUERY_CHARS = 100      # longest zero-result text kept
STAGES = ("spelling", "keyword", "semantic", "reranker", "total")
REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


# ------------------------------------------------------------------ logs

def _request_logger():
    logger = logging.getLogger("semantic.requests")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


request_log = _request_logger()


def log_event(level, **fields):
    record = {"time": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "level": level, **fields}
    request_log.log(logging.ERROR if level == "error" else logging.INFO, json.dumps(record, default=str))


# ------------------------------------------------------------------ one request

@dataclass
class RequestRecord:
    """What one request did; filled in by timed search steps."""
    request_id: str
    started: float = field(default_factory=perf_counter)
    stages: dict = field(default_factory=lambda: defaultdict(float))
    active: set = field(default_factory=set)
    details: dict = field(default_factory=dict)


current_request = ContextVar("observability_request", default=None)


def request_id_from(header):
    """Reuse a caller's request ID when it is well formed, otherwise make one."""
    return header if header and REQUEST_ID.match(header) else uuid4().hex[:16]


def keep_best_score(record, scores):
    """Remember the best careful-check score this request saw (no extra work)."""
    try:
        best = max(float(score) for score in scores)
    except (TypeError, ValueError):
        return
    record.details["topScore"] = round(max(best, record.details.get("topScore", best)), 2)


def timed(stage, function, observe=None):
    """Wrap a search step so its time is added to the current request.

    Nested calls of the same step (spelling.alternatives calls spelling.correct)
    are counted once. Calls outside a request are not recorded. `observe`, when
    given, also sees the step's result."""
    if getattr(function, "_observed", False):
        return function

    @wraps(function)
    def wrapper(*args, **kwargs):
        record = current_request.get()
        if record is None or stage in record.active:
            return function(*args, **kwargs)
        record.active.add(stage)
        start = perf_counter()
        try:
            result = function(*args, **kwargs)
            if observe is not None:
                observe(record, result)
            return result
        finally:
            record.active.discard(stage)
            record.stages[stage] += (perf_counter() - start) * 1000

    wrapper._observed = True
    return wrapper


_instrument_lock = Lock()


def instrument(target, stage, method, observe=None):
    """Time `target.method` in place; safe to call again."""
    if target is None:
        return
    with _instrument_lock:
        function = getattr(target, method, None)
        if callable(function) and getattr(function, "_observed", False) is not True:
            setattr(target, method, timed(stage, function, observe))


def instrument_engines(engine, ranker):
    """Time each search step without changing the search code itself."""
    if engine is not None:
        instrument(getattr(engine, "spelling", None), "spelling", "correct")
        instrument(getattr(engine, "spelling", None), "spelling", "alternatives")
        instrument(getattr(engine, "hybrid", None), "retrieval", "search")
        instrument(getattr(engine, "semantic", None), "semantic", "search")
    if ranker is not None:
        instrument(getattr(ranker, "encoder", None), "semantic", "encode")
        instrument(getattr(ranker, "reranker", None), "reranker", "predict", keep_best_score)


# ------------------------------------------------------------------ metrics

def _summary(values):
    values = list(values)
    if not values:
        return {"count": 0, "p50": None, "p95": None}
    return {"count": len(values), "p50": round(percentile(values, 0.5), 1), "p95": round(percentile(values, 0.95), 1)}


def search_stages(stages, total_ms):
    """Per-step milliseconds for one search; keyword time is retrieval minus meaning search."""
    retrieval = stages.get("retrieval")
    semantic = stages.get("semantic")
    keyword = None if retrieval is None else max(0.0, retrieval - (semantic or 0.0))
    values = {"spelling": stages.get("spelling"), "keyword": keyword, "semantic": semantic,
              "reranker": stages.get("reranker"), "total": total_ms}
    return {name: round(value, 2) for name, value in values.items() if value is not None}


class Metrics:
    """Bounded live numbers for the System health page."""

    def __init__(self):
        self.lock = Lock()
        self.reset()

    def reset(self):
        with self.lock:
            self.started_at = time()
            self.requests = 0
            self.errors = 0
            self.statuses = Counter()
            self.routes = defaultdict(lambda: {"count": 0, "errors": 0, "timings": deque(maxlen=ROUTE_WINDOW)})
            self.searches = Counter()
            self.zero_results = Counter()
            self.no_good_match = Counter()
            self.search_timings = deque(maxlen=WINDOW)
            self.zero_queries = deque(maxlen=ZERO_KEEP)

    def record_request(self, route, status, duration_ms):
        with self.lock:
            self.requests += 1
            self.statuses[f"{status // 100}xx"] += 1
            entry = self.routes[route]
            entry["count"] += 1
            entry["timings"].append(duration_ms)
            if status >= 500:
                self.errors += 1
                entry["errors"] += 1

    def record_search(self, source, query, stages, reason):
        """One finished search. Texts of searches that found nothing good are
        kept without any user ID."""
        with self.lock:
            self.searches[source] += 1
            self.search_timings.append(stages)
            if reason == "no-results":
                self.zero_results[source] += 1
            elif reason == "no-close-match":
                self.no_good_match[source] += 1
            if reason:
                self.zero_queries.append((" ".join(query.split())[:QUERY_CHARS], source, time(), reason))

    def snapshot(self, include_queries):
        with self.lock:
            searches = sum(self.searches.values())
            zero = sum(self.zero_results.values())
            weak = sum(self.no_good_match.values())
            routes = sorted(self.routes.items(), key=lambda item: -item[1]["count"])[:12]
            return {
                "startedAt": datetime.fromtimestamp(self.started_at, timezone.utc).isoformat(timespec="seconds"),
                "uptimeSeconds": round(time() - self.started_at),
                "limits": {"searchWindow": WINDOW, "zeroResultTexts": ZERO_KEEP},
                "requests": {"total": self.requests, "errors": self.errors,
                             "errorRate": self.errors / self.requests if self.requests else 0.0,
                             "byStatus": dict(self.statuses)},
                "routes": [{"route": route, "count": entry["count"], "errors": entry["errors"],
                            **{k: v for k, v in _summary(entry["timings"]).items() if k != "count"}}
                           for route, entry in routes],
                "search": {
                    "total": searches, "bySource": dict(self.searches),
                    "zeroResults": zero, "noCloseMatch": weak,
                    "missRate": (zero + weak) / searches if searches else 0.0,
                    "closeMatchFloor": RELEVANCE_THRESHOLD,
                    "stages": {stage: _summary(t[stage] for t in self.search_timings if stage in t) for stage in STAGES},
                },
                "zeroResultSearches": self._zero_summary() if include_queries else None,
            }

    def _zero_summary(self, limit=25):
        """Most frequent missed searches among those kept, newest first on ties."""
        counts, latest = Counter(), {}
        for text, source, when, reason in self.zero_queries:
            key = (" ".join(text.lower().split()), source)
            counts[key] += 1
            latest[key] = (text, when, reason)
        ordered = sorted(counts, key=lambda key: (-counts[key], -latest[key][1]))[:limit]
        return [{"query": latest[key][0], "source": key[1], "count": counts[key], "reason": latest[key][2],
                 "lastSeen": datetime.fromtimestamp(latest[key][1], timezone.utc).isoformat(timespec="seconds")}
                for key in ordered]


def miss_reason(result_count, top_probability):
    """Why a search found nothing good, or None when it did."""
    if result_count == 0:
        return "no-results"
    if top_probability is not None and top_probability < RELEVANCE_THRESHOLD:
        return "no-close-match"
    return None


metrics = Metrics()


def admin_ids():
    return {value.strip() for value in os.environ.get("OBSERVABILITY_ADMINS", "").split(",") if value.strip()}


# ------------------------------------------------------------------ middleware

def route_of(request):
    """The route template ("/api/saved/{item_id}"), never the raw path or query."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"


async def observe_requests(request, call_next):
    """Give each request an ID, time it, log one JSON line and count it."""
    record = RequestRecord(request_id_from(request.headers.get("x-request-id")))
    token = current_request.set(record)
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = record.request_id
        return response
    except Exception as error:
        log_event("error", event="unhandled_error", requestId=record.request_id,
                  route=route_of(request), error=type(error).__name__)
        raise
    finally:
        duration = round((perf_counter() - record.started) * 1000, 1)
        route = route_of(request)
        metrics.record_request(route, status, duration)
        log_event("error" if status >= 500 else "info", event="request", requestId=record.request_id,
                  method=request.method, route=route, status=status, durationMs=duration, **record.details)
        current_request.reset(token)


def record_search_outcome(source, payload, query):
    """Called when a search finishes: count it, keep its step timings and any zero result."""
    record = current_request.get()
    if record is None:
        return
    results = payload.get("results", []) if isinstance(payload, dict) else []
    probabilities = [item.get("relevanceProbability") for item in results]
    top_probability = max(probabilities) if probabilities and None not in probabilities else None
    total = (perf_counter() - record.started) * 1000
    stages = search_stages(record.stages, total)
    record.details.update(source=source, results=len(results), stagesMs=stages,
                          topRelevanceProbability=top_probability)
    # A blank search has nothing to find, so it is never counted as a miss.
    reason = miss_reason(len(results), top_probability) if query.strip() else None
    metrics.record_search(source, query, stages, reason)

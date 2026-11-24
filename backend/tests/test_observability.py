"""Observability: request IDs, JSON logs, bounded metrics and search step timings."""
import json
import logging
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from api import observability as obs


@pytest.fixture(autouse=True)
def fresh_metrics():
    obs.metrics.reset()
    yield
    obs.metrics.reset()


@pytest.fixture
def log_lines(caplog):
    obs.request_log.propagate = True
    caplog.set_level(logging.INFO, logger="semantic.requests")
    yield lambda: [json.loads(record.getMessage()) for record in caplog.records if record.name == "semantic.requests"]
    obs.request_log.propagate = False


# ---------------------------------------------------------------- requests

def test_each_request_gets_an_id_and_one_json_log_line_without_query_text(log_lines):
    from api import main
    client = TestClient(main.app)
    response = client.get("/healthz?q=private+search+text")
    request_id = response.headers["x-request-id"]
    assert len(request_id) == 16
    line = log_lines()[-1]
    assert line["requestId"] == request_id and line["route"] == "/healthz" and line["status"] == 200
    assert "private" not in json.dumps(line)            # query strings never reach the logs


def test_a_well_formed_caller_id_is_reused_and_bad_ones_replaced():
    from api import main
    client = TestClient(main.app)
    assert client.get("/healthz", headers={"X-Request-ID": "trace-1234-abcd"}).headers["x-request-id"] == "trace-1234-abcd"
    assert client.get("/healthz", headers={"X-Request-ID": "bad id\nwith newline"}).headers["x-request-id"] != "bad id\nwith newline"


def test_routes_are_recorded_by_template_and_unknown_paths_grouped():
    from api import main
    client = TestClient(main.app)
    client.get("/healthz")
    client.get("/does-not-exist/secret-value")
    routes = {row["route"]: row for row in obs.metrics.snapshot(False)["routes"]}
    assert routes["/healthz"]["count"] == 1
    assert routes["unmatched"]["count"] == 1 and "/does-not-exist/secret-value" not in routes


def test_server_errors_are_counted_and_logged(log_lines):
    obs.metrics.record_request("/api/x", 503, 12.0)
    obs.metrics.record_request("/api/x", 200, 8.0)
    requests = obs.metrics.snapshot(False)["requests"]
    assert requests["errors"] == 1 and requests["errorRate"] == 0.5
    assert requests["byStatus"] == {"5xx": 1, "2xx": 1}


# ---------------------------------------------------------------- memory stays bounded

def test_memory_is_capped_no_matter_how_many_searches():
    for index in range(obs.WINDOW + 250):
        obs.metrics.record_search("mongo", 0, f"query {index} " + "x" * 300, {"total": 10.0})
        obs.metrics.record_request("/api/search", 200, 10.0)
    assert len(obs.metrics.search_timings) == obs.WINDOW
    assert len(obs.metrics.zero_queries) == obs.ZERO_KEEP
    assert len(obs.metrics.routes["/api/search"]["timings"]) == obs.ROUTE_WINDOW
    assert all(len(text) <= obs.QUERY_CHARS for text, *_ in obs.metrics.zero_queries)


def test_zero_result_texts_are_grouped_and_hidden_unless_allowed():
    for query in ("blue fliptop", "Blue  fliptop", "rare thing"):
        obs.metrics.record_search("mongo", 0, query, {"total": 5.0})
    obs.metrics.record_search("shops", 3, "headphones", {"total": 5.0})
    obs.metrics.record_search("mongo", 0, "   ", {"total": 5.0})   # blank searches are not kept
    snapshot = obs.metrics.snapshot(include_queries=True)
    assert snapshot["search"]["zeroResults"] == 3 and snapshot["search"]["total"] == 5
    top = snapshot["zeroResultSearches"][0]
    assert top["count"] == 2 and top["query"].lower() == "blue fliptop" and top["source"] == "mongo"
    assert obs.metrics.snapshot(include_queries=False)["zeroResultSearches"] is None


def test_searches_with_only_weak_matches_count_as_no_close_match():
    floor = obs.RELEVANCE_FLOOR
    assert obs.miss_reason(0, None) == "no-results"
    assert obs.miss_reason(20, floor - 6) == "no-close-match"   # results exist, none is relevant
    assert obs.miss_reason(20, floor + 9) is None
    assert obs.miss_reason(20, None) is None                    # no reranker score: unknown, not a miss
    obs.metrics.record_search("mongo", 20, "qwxzv blorptastic", {"total": 5.0}, top_score=-11.3)
    obs.metrics.record_search("mongo", 20, "wireless headphones", {"total": 5.0}, top_score=4.8)
    snapshot = obs.metrics.snapshot(include_queries=True)
    assert snapshot["search"]["noCloseMatch"] == 1 and snapshot["search"]["missRate"] == 0.5
    assert snapshot["zeroResultSearches"] == [{**snapshot["zeroResultSearches"][0], "query": "qwxzv blorptastic",
                                               "reason": "no-close-match", "count": 1}]


def test_the_reranker_wrapper_keeps_the_best_score_of_the_request():
    reranker = Mock()
    reranker.predict = lambda pairs, **_: [-9.0, 3.5]
    obs.instrument_engines(None, Mock(encoder=None, reranker=reranker))
    record = obs.RequestRecord("score-request")
    token = obs.current_request.set(record)
    try:
        reranker.predict([("q", "a"), ("q", "b")])
    finally:
        obs.current_request.reset(token)
    assert record.details["topScore"] == 3.5 and "reranker" in record.stages


# ---------------------------------------------------------------- search step timings

class Spelling:
    def correct(self, query):
        return query, []

    def alternatives(self, query):
        self.correct(query)            # nested: must be counted once
        return [query]


def test_steps_are_timed_once_and_only_inside_a_request():
    engine = Mock(spelling=Spelling(), hybrid=Mock(), semantic=Mock())
    engine.hybrid.search = lambda *a, **k: engine.semantic.search()
    engine.semantic.search = lambda *a, **k: []
    obs.instrument_engines(engine, None)
    obs.instrument_engines(engine, None)       # instrumenting again changes nothing
    assert engine.spelling.alternatives("x") == ["x"]   # outside a request: just runs

    record = obs.RequestRecord("test-request-id")
    token = obs.current_request.set(record)
    try:
        engine.spelling.alternatives("x")
        engine.hybrid.search("x")
    finally:
        obs.current_request.reset(token)
    assert set(record.stages) == {"spelling", "retrieval", "semantic"}
    stages = obs.search_stages(record.stages, 100.0)
    assert stages["keyword"] == pytest.approx(max(0.0, record.stages["retrieval"] - record.stages["semantic"]), abs=0.01)
    assert stages["total"] == 100.0


def test_search_outcomes_record_counts_and_log_details():
    record = obs.RequestRecord("search-request")
    record.stages.update({"retrieval": 30.0, "semantic": 20.0, "reranker": 50.0})
    token = obs.current_request.set(record)
    try:
        obs.record_search_outcome("mongo", {"results": []}, "zzz nothing")
    finally:
        obs.current_request.reset(token)
    assert record.details["results"] == 0 and record.details["stagesMs"]["keyword"] == 10.0
    assert "query" not in record.details                       # search text never goes to the log line
    summary = obs.metrics.snapshot(True)
    assert summary["search"]["stages"]["reranker"]["p50"] == 50.0
    assert summary["zeroResultSearches"][0]["query"] == "zzz nothing"
    obs.record_search_outcome("mongo", {"results": []}, "outside request")   # ignored, no crash
    assert obs.metrics.snapshot(True)["search"]["total"] == 1


# ---------------------------------------------------------------- endpoint

def test_health_endpoint_hides_search_text_from_non_admins(authenticated_api, monkeypatch):
    from api import main
    obs.metrics.record_search("mongo", 0, "secret zero result", {"total": 5.0})
    client = TestClient(main.app)
    monkeypatch.setenv("OBSERVABILITY_ADMINS", "someone_else")
    body = client.get("/api/observability").json()
    assert body["zeroResultSearches"] is None
    assert body["viewer"] == {"userId": "user_test", "canSeeSearchText": False}
    monkeypatch.setenv("OBSERVABILITY_ADMINS", "someone_else, user_test")
    body = client.get("/api/observability").json()
    assert body["viewer"]["canSeeSearchText"] is True
    assert body["zeroResultSearches"][0]["query"] == "secret zero result"


def test_health_endpoint_requires_sign_in():
    from api import main
    assert TestClient(main.app).get("/api/observability").status_code == 401


def test_a_real_search_request_is_measured(authenticated_api):
    from api import main
    engine = Mock()
    engine.search.return_value = {"results": [], "candidateCount": 0}
    with patch.object(main, "search_initializing", return_value=False), \
            patch.object(main, "get_search_engine", return_value=engine), \
            patch.object(main, "with_product_links", side_effect=lambda payload: payload):
        TestClient(main.app).get("/api/search", params={"q": "unfindable thing"})
    summary = obs.metrics.snapshot(True)
    assert summary["search"]["total"] == 1 and summary["search"]["zeroResults"] == 1
    assert summary["zeroResultSearches"][0]["query"] == "unfindable thing"
    assert summary["search"]["stages"]["total"]["count"] == 1

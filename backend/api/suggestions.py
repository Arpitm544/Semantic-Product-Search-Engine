"""Search suggestions while typing: the shopper's own recent searches, brands
and catalog phrases. Other shoppers' searches are never suggested."""
from collections import OrderedDict
import logging
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends, Query
from pymongo.errors import PyMongoError

from api.auth import require_session
from api import search_history, search_service
from src.search.autocomplete import Autocomplete, normalize

router = APIRouter(tags=["Search suggestions"])
logger = logging.getLogger(__name__)

LIMIT = 8
MAX_RECENT = 3
MAX_BRANDS = 2
RECENT_FETCH = 50      # latest searches kept per shopper for matching
RECENT_TTL = 30        # seconds before a shopper's history is read again
RECENT_USERS = 1000    # shoppers kept in memory, least recently used dropped first
_recent = OrderedDict()
_recent_lock = Lock()
_cache = {"products": None, "index": None}
_cache_lock = Lock()


def autocomplete_for(products):
    """Build the phrase index once per catalog list (about five seconds)."""
    if not isinstance(products, list) or not products:
        return None
    with _cache_lock:
        if _cache["products"] is not products:
            _cache.update(products=products, index=Autocomplete(products))
        return _cache["index"]


def warm_up(engine):
    """Build suggestions right after search starts, so the first keystroke is fast."""
    try:
        autocomplete_for(getattr(engine, "products", None))
    except (TypeError, KeyError, AttributeError, ValueError):
        logger.exception("Search suggestions could not be prepared")


def load_recent(user_id):
    """The shopper's latest distinct searches, newest first (one database read)."""
    rows = search_history.collection().find({"user_id": user_id}, {"query": 1, "_id": 0}) \
        .sort([("searched_at", -1)]).limit(RECENT_FETCH)
    return list(dict.fromkeys(row["query"] for row in rows))


def cached_recent(user_id):
    """Read history once per shopper every few seconds, not on every keystroke."""
    now = monotonic()
    with _recent_lock:
        hit = _recent.get(user_id)
        if hit and now - hit[0] < RECENT_TTL:
            _recent.move_to_end(user_id)
            return hit[1]
    queries = load_recent(user_id)
    with _recent_lock:
        _recent[user_id] = (now, queries)
        _recent.move_to_end(user_id)
        while len(_recent) > RECENT_USERS:
            _recent.popitem(last=False)
    return queries


def recent_matches(user_id, typed, limit=MAX_RECENT):
    """The shopper's own recent searches that start with what they typed."""
    prefix = normalize(typed).strip()
    try:
        queries = cached_recent(user_id)
    except PyMongoError:
        # Suggestions still work from the catalog when history is unavailable.
        logger.warning("Recent searches unavailable for suggestions", exc_info=True)
        return []
    return [query for query in queries if normalize(query).startswith(prefix)][:limit]


def merge(groups, limit=LIMIT):
    """Combine suggestion groups in order, without repeats (ignoring case)."""
    seen, merged = set(), []
    for kind, texts in groups:
        for text in texts:
            key = normalize(text).strip()
            if key and key not in seen and len(merged) < limit:
                seen.add(key)
                merged.append({"text": text, "kind": kind})
    return merged


@router.get("/api/suggest")
def suggest(q: str = Query("", max_length=200), session=Depends(require_session)):
    """Up to eight suggestions. Empty while search is still starting up."""
    typed = q.strip()
    if len(normalize(typed)) < 2:
        return {"query": q, "suggestions": []}
    engine = search_service._search_engine
    index = autocomplete_for(engine.products if engine else None)
    groups = [("recent", recent_matches(session["sub"], typed))]
    if index is not None:
        groups += [("brand", index.brand_matches(typed, MAX_BRANDS)), ("catalog", index.complete(q, LIMIT))]
    return {"query": q, "suggestions": merge(groups)}

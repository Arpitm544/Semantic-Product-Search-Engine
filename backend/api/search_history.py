"""Private, persistent recent searches and personal dashboard summaries."""
from datetime import datetime, timezone
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.errors import PyMongoError

from api.auth import require_session
from api import saved_products
from src.data.db import get_database

router = APIRouter(tags=["Personal dashboard"])
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def collection():
    result = get_database()["search_history"]
    result.create_index([("user_id", 1), ("searched_at", -1), ("_id", 1)])
    return result


def public_entry(item):
    date = item["searched_at"]
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return {"id": item["_id"], "query": item["query"], "source": item["source"],
            "fuzzy": item["fuzzy"], "usePreferences": item.get("use_preferences", False), "resultCount": item["result_count"],
            "searchedAt": date.isoformat()}


def recent_entries(user_id, offset=0, limit=6):
    items = list(collection().find({"user_id": user_id}).sort(
        [("searched_at", -1), ("_id", 1)]).skip(offset).limit(limit + 1))
    return {"items": [public_entry(item) for item in items[:limit]], "hasMore": len(items) > limit}


@dataclass(frozen=True)
class SearchContext:
    query: str
    source: str = "mongo"
    fuzzy: bool = True
    use_preferences: bool = False


def remember_search(user_id, search, payload):
    """A failed history write must never discard successful search results."""
    query, source, fuzzy = search.query, search.source, search.fuzzy
    use_preferences = search.use_preferences
    if not query:
        return payload
    identity = [user_id, query, source, fuzzy]
    if use_preferences:
        identity.append('preferences')
    key = sha256(json.dumps(identity).encode()).hexdigest()
    try:
        collection().update_one({"_id": key, "user_id": user_id}, {"$set": {
            "user_id": user_id, "query": query, "source": source, "fuzzy": fuzzy,
            "use_preferences": use_preferences, "result_count": len(payload.get("results", [])), "searched_at": datetime.now(timezone.utc),
        }}, upsert=True)
        return {**payload, "historySaved": True}
    except PyMongoError:
        logger.warning("Could not persist search history")
        return {**payload, "historySaved": False}


@router.get("/api/search-history")
def list_history(offset: int = Query(0, ge=0, le=100000), limit: int = Query(6, ge=1, le=50),
                 session=Depends(require_session)):
    try:
        return recent_entries(session["sub"], offset, limit)
    except PyMongoError:
        raise HTTPException(503, "Search history is temporarily unavailable. Please try again.") from None


@router.delete("/api/search-history")
def clear_history(session=Depends(require_session)):
    try:
        collection().delete_many({"user_id": session["sub"]})
        return {"ok": True}
    except PyMongoError:
        raise HTTPException(503, "Could not clear search history. Please try again.") from None


@router.delete("/api/search-history/{entry_id}")
def delete_entry(entry_id: str, session=Depends(require_session)):
    try:
        collection().delete_one({"_id": entry_id, "user_id": session["sub"]})
        return {"ok": True}
    except PyMongoError:
        raise HTTPException(503, "Could not remove this search. Please try again.") from None


@router.get("/api/personal-dashboard")
def personal_dashboard(session=Depends(require_session)):
    user_id = session["sub"]
    owner = {"user_id": user_id}
    try:
        history = recent_entries(user_id)
        saved = saved_products.collection()
        previews = list(saved.find(owner).sort([("saved_at", -1), ("_id", 1)]).limit(4))
        return {"searchCount": collection().count_documents(owner),
                "savedCount": saved.count_documents(owner),
                "recentSearches": history["items"], "hasMoreSearches": history["hasMore"],
                "savedProducts": [saved_products.public_item(item) for item in previews]}
    except PyMongoError:
        raise HTTPException(503, "Your dashboard is temporarily unavailable. Please try again.") from None

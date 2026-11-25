"""Atomic, shared per-user fixed-window search limits."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from hashlib import sha256
import os
from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError
from src.data.db import get_database


@lru_cache(maxsize=1)
def collection():
    value = get_database()['search_rate_limits']
    value.create_index('expires_at', expireAfterSeconds=0)
    return value


def _increment_window(key, limit, expires_at):
    query = {'_id': key, 'count': {'$lt': limit}}
    update = {'$inc': {'count': 1}, '$setOnInsert': {'expires_at': expires_at}}
    try:
        return collection().find_one_and_update(
            query, update, upsert=True, return_document=ReturnDocument.AFTER)
    except DuplicateKeyError:
        # Two requests can race to create the first counter document of a window;
        # retry once against the newly inserted document before treating it as full.
        return collection().find_one_and_update(
            query, {'$inc': {'count': 1}}, upsert=False, return_document=ReturnDocument.AFTER)


def take_daily_slot(scope, limit):
    """Atomically use one of `limit` slots for `scope` in the current UTC day.

    Returns False when the day's slots are used up. Database errors propagate.
    """
    if limit <= 0:
        return False
    timestamp = datetime.now(timezone.utc)
    day = int(timestamp.timestamp()) // 86400
    key = sha256(f'daily:{scope}:{day}'.encode()).hexdigest()
    try:
        result = _increment_window(key, limit, timestamp + timedelta(days=2))
    except DuplicateKeyError:
        return False
    return result is not None


RATE_SETTINGS = {
    'serpapi': ('SHOPPING_SEARCHES_PER_MINUTE', 5),
    'shops': ('SHOPS_SEARCHES_PER_MINUTE', 10),
}


def check_search_rate(user, source):
    name, default = RATE_SETTINGS.get(source, ('CATALOG_SEARCHES_PER_MINUTE', 30))
    try:
        limit = max(1, int(os.environ.get(name, str(default))))
    except ValueError:
        limit = default
    timestamp = datetime.now(timezone.utc)
    window = int(timestamp.timestamp()) // 60
    key = sha256(f'{user}:{source}:{window}'.encode()).hexdigest()
    try:
        result = _increment_window(key, limit, timestamp + timedelta(minutes=2))
        if result is None:
            raise DuplicateKeyError('Rate limit reached')
    except DuplicateKeyError:
        retry = max(1, 60 - int(timestamp.timestamp()) % 60)
        raise HTTPException(429, 'Too many searches. Please wait before trying again.', headers={'Retry-After': str(retry)}) from None
    except PyMongoError:
        raise HTTPException(503, 'Search limits are temporarily unavailable. Please try again.') from None

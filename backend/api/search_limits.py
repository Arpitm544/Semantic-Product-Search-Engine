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
        result = collection().find_one_and_update({'_id': key, 'count': {'$lt': limit}},
            {'$inc': {'count': 1}, '$setOnInsert': {'expires_at': timestamp + timedelta(days=2)}},
            upsert=True, return_document=ReturnDocument.AFTER)
    except DuplicateKeyError:
        return False
    return result is not None


def check_search_rate(user, source):
    try:
        limit = max(1, int(os.environ.get('SHOPPING_SEARCHES_PER_MINUTE' if source == 'serpapi' else 'CATALOG_SEARCHES_PER_MINUTE', '5' if source == 'serpapi' else '30')))
    except ValueError:
        limit = 5 if source == 'serpapi' else 30
    timestamp = datetime.now(timezone.utc)
    window = int(timestamp.timestamp()) // 60
    key = sha256(f'{user}:{source}:{window}'.encode()).hexdigest()
    try:
        result = collection().find_one_and_update({'_id': key, 'count': {'$lt': limit}},
            {'$inc': {'count': 1}, '$setOnInsert': {'expires_at': timestamp + timedelta(minutes=2)}},
            upsert=True, return_document=ReturnDocument.AFTER)
        if result is None:
            raise DuplicateKeyError('Rate limit reached')
    except DuplicateKeyError:
        retry = max(1, 60 - int(timestamp.timestamp()) % 60)
        raise HTTPException(429, 'Too many searches. Please wait before trying again.', headers={'Retry-After': str(retry)}) from None
    except PyMongoError:
        raise HTTPException(503, 'Search limits are temporarily unavailable. Please try again.') from None

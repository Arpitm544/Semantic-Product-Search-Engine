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

"""Shared storage and validation for private account features."""
from datetime import datetime, timezone
from functools import lru_cache
from uuid import uuid4

from fastapi import HTTPException
from fastapi.routing import APIRoute
from pymongo.errors import PyMongoError
from src.data.db import get_database


class PrivateDataRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def safe_handler(request):
            try:
                return await handler(request)
            except PyMongoError:
                raise HTTPException(503, "Your account data is temporarily unavailable. Please try again.") from None
        return safe_handler


def now():
    return datetime.now(timezone.utc)


def iso(date):
    if date is None:
        return None
    return date.replace(tzinfo=date.tzinfo or timezone.utc).isoformat()


@lru_cache(maxsize=8)
def store(name):
    if name not in {'product_collections', 'user_preferences', 'saved_comparisons', 'price_alerts', 'price_notifications'}:
        raise ValueError('Unknown account collection')
    result = get_database()[name]
    result.create_index([('user_id', 1), ('updated_at', -1), ('_id', 1)])
    if name == 'price_alerts':
        result.create_index([('enabled', 1), ('next_check_at', 1)])
    return result


def owned(name, identifier, user):
    result = store(name).find_one({'_id': identifier, 'user_id': user})
    if result is None:
        raise HTTPException(404, 'Item not found.')
    return result


def saved_items(user, identifiers):
    from api import saved_products
    rows = list(saved_products.collection().find({'user_id': user, '_id': {'$in': identifiers}}))
    by_id = {row['_id']: row for row in rows}
    if len(by_id) != len(set(identifiers)):
        raise HTTPException(404, 'One or more saved products are unavailable.')
    return [by_id[key] for key in identifiers]


def new_id():
    return uuid4().hex


def clean_saved_links(user, identifier):
    store('product_collections').update_many({'user_id': user, 'product_ids': identifier},
        {'$pull': {'product_ids': identifier}, '$set': {'updated_at': now()}})
    store('price_alerts').update_many({'user_id': user, 'saved_id': identifier},
        {'$set': {'enabled': False, 'status': 'saved_product_removed', 'revision': new_id()}})

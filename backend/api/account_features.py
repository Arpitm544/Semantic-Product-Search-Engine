"""Collections, persisted search preferences, and snapshot comparisons."""
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from api.product_prices import CURRENCIES
from api.auth import require_session
from api.account_store import PrivateDataRoute, store, owned, saved_items, new_id, now, iso
from api import saved_products

router = APIRouter(route_class=PrivateDataRoute, dependencies=[Depends(require_session)])
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Identifier = Annotated[str, StringConstraints(pattern=r'^[a-f0-9]{32,64}$')]


class Named(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: ShortText


class ComparisonInput(Named):
    savedIds: list[Identifier] = Field(min_length=2, max_length=4)

    @model_validator(mode='after')
    def distinct(self):
        if len(set(self.savedIds)) != len(self.savedIds):
            raise ValueError('Choose different saved products.')
        return self


class Preferences(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    defaultSource: Literal['mongo', 'serpapi'] = 'mongo'
    applyByDefault: bool = False
    currency: str = Field(default='INR', pattern=r'^[A-Z]{3}$')
    minBudget: Optional[float] = Field(default=None, ge=0, le=1e12)
    maxBudget: Optional[float] = Field(default=None, ge=0, le=1e12)
    categories: list[ShortText] = Field(default_factory=list, max_length=20)
    brands: list[ShortText] = Field(default_factory=list, max_length=20)
    inStockOnly: bool = False

    @field_validator('currency')
    @classmethod
    def supported_currency(cls, value):
        if value not in CURRENCIES:
            raise ValueError('Choose a supported currency.')
        return value

    @model_validator(mode='after')
    def valid_budget(self):
        if self.minBudget is not None and self.maxBudget is not None and self.minBudget > self.maxBudget:
            raise ValueError('Minimum budget must not exceed maximum budget.')
        self.categories = list(dict.fromkeys(self.categories))
        self.brands = list(dict.fromkeys(self.brands))
        return self


def load_preferences(user):
    row = store('user_preferences').find_one({'_id': user, 'user_id': user})
    return Preferences.model_validate(row['preferences'] if row else {}).model_dump()


@router.get('/api/preferences')
def get_preferences(session=Depends(require_session)):
    return load_preferences(session['sub'])


@router.put('/api/preferences')
def put_preferences(body: Preferences, session=Depends(require_session)):
    user = session['sub']
    value = body.model_dump()
    store('user_preferences').update_one({'_id': user, 'user_id': user},
        {'$set': {'preferences': value, 'updated_at': now()}}, upsert=True)
    return value


@router.delete('/api/preferences')
def reset_preferences(session=Depends(require_session)):
    user = session['sub']
    store('user_preferences').delete_one({'_id': user, 'user_id': user})
    return Preferences().model_dump()


def collection_summary(row):
    return {'id': row['_id'], 'name': row['name'], 'productIds': row.get('product_ids', []), 'updatedAt': iso(row['updated_at'])}


@router.get('/api/collections')
def list_collections(offset: int = Query(0, ge=0, le=100000), session=Depends(require_session)):
    rows = list(store('product_collections').find({'user_id': session['sub']}).sort([('updated_at', -1), ('_id', 1)]).skip(offset).limit(51))
    return {'items': [collection_summary(row) for row in rows[:50]], 'hasMore': len(rows) > 50}


@router.post('/api/collections', status_code=201)
def create_collection(body: Named, session=Depends(require_session)):
    row = {'_id': new_id(), 'user_id': session['sub'], 'name': body.name, 'product_ids': [], 'updated_at': now()}
    store('product_collections').insert_one(row)
    return collection_summary(row)


@router.get('/api/collections/{identifier}')
def collection_detail(identifier: str, session=Depends(require_session)):
    user = session['sub']
    row = owned('product_collections', identifier, user)
    items = list(saved_products.collection().find({'user_id': user, '_id': {'$in': row.get('product_ids', [])}}))
    return {**collection_summary(row), 'items': [saved_products.public_item(item) for item in items]}


@router.patch('/api/collections/{identifier}')
def rename_collection(identifier: str, body: Named, session=Depends(require_session)):
    user = session['sub']
    owned('product_collections', identifier, user)
    store('product_collections').update_one({'_id': identifier, 'user_id': user}, {'$set': {'name': body.name, 'updated_at': now()}})
    return {'ok': True}


@router.delete('/api/collections/{identifier}')
def delete_collection(identifier: str, session=Depends(require_session)):
    store('product_collections').delete_one({'_id': identifier, 'user_id': session['sub']})
    return {'ok': True}


@router.put('/api/collections/{identifier}/products/{saved_id}')
def add_collection_product(identifier: str, saved_id: str, session=Depends(require_session)):
    user = session['sub']
    row = owned('product_collections', identifier, user)
    saved_items(user, [saved_id])
    if saved_id in row.get('product_ids', []):
        return {'ok': True}
    updated = store('product_collections').update_one(
        {'_id': identifier, 'user_id': user, '$expr': {'$lt': [{'$size': '$product_ids'}, 100]}},
        {'$addToSet': {'product_ids': saved_id}, '$set': {'updated_at': now()}})
    if not updated.matched_count:
        raise HTTPException(409, 'This collection can hold up to 100 products.')
    return {'ok': True}


@router.delete('/api/collections/{identifier}/products/{saved_id}')
def remove_collection_product(identifier: str, saved_id: str, session=Depends(require_session)):
    store('product_collections').update_one({'_id': identifier, 'user_id': session['sub']},
        {'$pull': {'product_ids': saved_id}, '$set': {'updated_at': now()}})
    return {'ok': True}


def comparison_summary(row):
    return {'id': row['_id'], 'name': row['name'], 'products': row['products'], 'updatedAt': iso(row['updated_at'])}


def comparison_products(user, ids):
    return [{'savedId': row['_id'], 'source': row['source'], 'product': row['product']} for row in saved_items(user, ids)]


@router.get('/api/comparisons')
def list_comparisons(offset: int = Query(0, ge=0, le=100000), session=Depends(require_session)):
    rows = list(store('saved_comparisons').find({'user_id': session['sub']}).sort([('updated_at', -1), ('_id', 1)]).skip(offset).limit(21))
    return {'items': [comparison_summary(row) for row in rows[:20]], 'hasMore': len(rows) > 20}


@router.post('/api/comparisons', status_code=201)
def create_comparison(body: ComparisonInput, session=Depends(require_session)):
    row = {'_id': new_id(), 'user_id': session['sub'], 'name': body.name,
           'products': comparison_products(session['sub'], body.savedIds), 'updated_at': now()}
    store('saved_comparisons').insert_one(row)
    return comparison_summary(row)


@router.patch('/api/comparisons/{identifier}')
def rename_comparison(identifier: str, body: Named, session=Depends(require_session)):
    user = session['sub']
    owned('saved_comparisons', identifier, user)
    store('saved_comparisons').update_one({'_id': identifier, 'user_id': user}, {'$set': {'name': body.name, 'updated_at': now()}})
    return {'ok': True}


@router.delete('/api/comparisons/{identifier}')
def delete_comparison(identifier: str, session=Depends(require_session)):
    store('saved_comparisons').delete_one({'_id': identifier, 'user_id': session['sub']})
    return {'ok': True}


@router.get('/api/account-overview')
def account_overview(session=Depends(require_session)):
    owner = {'user_id': session['sub']}
    rows = list(store('product_collections').find(owner).sort([('updated_at', -1), ('_id', 1)]).limit(3))
    return {'collectionCount': store('product_collections').count_documents(owner),
            'comparisonCount': store('saved_comparisons').count_documents(owner),
            'activeAlertCount': store('price_alerts').count_documents({**owner, 'enabled': True}),
            'unreadAlertCount': store('price_notifications').count_documents({**owner, 'read': False}),
            'collections': [collection_summary(row) for row in rows]}

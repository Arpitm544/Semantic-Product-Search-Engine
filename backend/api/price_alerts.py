"""Opt-in price monitoring with bounded, leased checks and in-app notifications."""
from datetime import timedelta
from hashlib import sha256
import logging
import os
import re
from threading import Event
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

from api.auth import require_session
from api.account_store import PrivateDataRoute, store, saved_items, owned, now, iso, new_id
from api.product_prices import price_info
from api.shopping_service import search_shopping, ShoppingError
from src.data import catalog

logger = logging.getLogger(__name__)
router = APIRouter(route_class=PrivateDataRoute, dependencies=[Depends(require_session)])


def interval_seconds():
    try:
        return max(3600, int(os.environ.get('PRICE_ALERT_INTERVAL_SECONDS', '21600')))
    except ValueError:
        return 21600


def market_settings():
    return {name: os.environ.get(name, default) for name, default in (
        ('SERPAPI_COUNTRY', 'in'), ('SERPAPI_LANGUAGE', 'en'), ('SERPAPI_LOCATION', ''))}


def eligibility(saved):
    price = price_info(saved['product'])
    if not price or price['amount'] <= 0:
        return None, 'A positive numeric price and an unambiguous currency are required.'
    if saved['source'] == 'serpapi':
        if not re.fullmatch(r'serpapi:\d{5,}', saved['identity']) or not saved['product'].get('merchant'):
            return None, 'This offer has no stable product ID and merchant for price checks.'
    return price, None


class AlertInput(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    savedId: str = Field(pattern=r'^[a-f0-9]{64}$')
    targetPrice: Optional[float] = Field(default=None, gt=0, le=1e12)


class AlertUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool


def public_alert(row):
    return {'id': row['_id'], 'savedId': row['saved_id'], 'title': row['product']['title'],
            'source': row['source'], 'currency': row['currency'], 'baselinePrice': row['baseline_price'],
            'targetPrice': row['target_price'], 'currentPrice': row.get('current_price'),
            'enabled': row['enabled'], 'status': row.get('status', 'pending'),
            'message': row.get('message'), 'lastCheckedAt': iso(row.get('last_checked_at')),
            'nextCheckAt': iso(row.get('next_check_at'))}


@router.get('/api/price-alerts/eligibility/{saved_id}')
def alert_eligibility(saved_id: str, session=Depends(require_session)):
    item = saved_items(session['sub'], [saved_id])[0]
    price, reason = eligibility(item)
    return {'eligible': price is not None, 'price': price, 'reason': reason}


@router.get('/api/price-alerts')
def list_alerts(offset: int = Query(0, ge=0, le=100000), session=Depends(require_session)):
    rows = list(store('price_alerts').find({'user_id': session['sub']}).sort([('updated_at', -1), ('_id', 1)]).skip(offset).limit(51))
    return {'items': [public_alert(row) for row in rows[:50]], 'hasMore': len(rows) > 50,
            'intervalSeconds': interval_seconds(), 'schedulerEnabled': os.environ.get('PRICE_ALERTS_ENABLED', '1') == '1'}


@router.put('/api/price-alerts')
def create_alert(body: AlertInput, session=Depends(require_session)):
    user = session['sub']
    item = saved_items(user, [body.savedId])[0]
    price, reason = eligibility(item)
    if reason:
        raise HTTPException(422, reason)
    target = body.targetPrice if body.targetPrice is not None else price['amount']
    if target > price['amount']:
        raise HTTPException(422, 'Target price must not exceed the saved price.')
    identifier = sha256(f'{user}:{body.savedId}'.encode()).hexdigest()
    previous = store('price_alerts').find_one({'_id': identifier, 'user_id': user})
    if previous:
        raise HTTPException(409, 'An alert already exists for this product. Manage it below.')
    if store('price_alerts').count_documents({'user_id': user, 'enabled': True}) >= 50:
        raise HTTPException(409, 'Pause or remove an alert before enabling more than 50 active alerts.')
    timestamp = now()
    row = {'_id': identifier, 'user_id': user, 'saved_id': body.savedId,
           'product': item['product'], 'source': item['source'], 'identity': item['identity'],
           'currency': price['currency'], 'baseline_price': price['amount'], 'min_price': price['amount'],
           'target_price': target, 'enabled': True, 'status': 'pending', 'market': market_settings(),
           'revision': new_id(), 'next_check_at': timestamp, 'updated_at': timestamp}
    store('price_alerts').update_one({'_id': identifier, 'user_id': user}, {'$setOnInsert': row}, upsert=True)
    return public_alert(owned('price_alerts', identifier, user))


@router.patch('/api/price-alerts/{identifier}')
def toggle_alert(identifier: str, body: AlertUpdate, session=Depends(require_session)):
    user = session['sub']
    row = owned('price_alerts', identifier, user)
    if body.enabled:
        saved_items(user, [row['saved_id']])
        if not row['enabled'] and store('price_alerts').count_documents({'user_id': user, 'enabled': True}) >= 50:
            raise HTTPException(409, 'Pause another alert before resuming more than 50 active alerts.')
    store('price_alerts').update_one({'_id': identifier, 'user_id': user},
        {'$set': {'enabled': body.enabled, 'revision': new_id(), 'updated_at': now()}})
    return {'ok': True}


@router.delete('/api/price-alerts/{identifier}')
def delete_alert(identifier: str, session=Depends(require_session)):
    store('price_alerts').delete_one({'_id': identifier, 'user_id': session['sub']})
    return {'ok': True}


def observe_price(alert):
    if alert['source'] == 'mongo':
        before = catalog.version()
        identities = [alert['identity']]
        if alert['identity'].isdigit() and len(alert['identity']) < 20:
            identities.append(int(alert['identity']))
        product = catalog.database()[catalog.COLLECTION].find_one({'id': {'$in': identities}}, {'_id': 0})
        if catalog.version() != before:
            raise ValueError('The catalog is updating. A later check will retry.')
        if product is None:
            raise ValueError('This product is no longer available in the catalog.')
    else:
        if alert['market'] != market_settings():
            raise ValueError('Shopping region settings changed. Recreate this alert for the new region.')
        candidates = search_shopping(alert['product']['title'])['results']
        product = next((item for item in candidates if str(item.get('id')) == alert['identity']
                        and str(item.get('merchant') or '').casefold() == alert['product']['merchant'].casefold()), None)
        if product is None:
            raise ValueError('The same product and merchant could not be verified. A later check will retry.')
    quote = price_info(product)
    if not quote or quote['currency'] != alert['currency']:
        raise ValueError('A comparable price in the original currency is unavailable.')
    return quote['amount']


def claim_due(identifier=None, user=None):
    timestamp = now()
    query = {'enabled': True, 'next_check_at': {'$lte': timestamp}}
    if identifier:
        query['_id'] = identifier
    if user:
        query['user_id'] = user
    return store('price_alerts').find_one_and_update(query,
        {'$set': {'next_check_at': timestamp + timedelta(seconds=interval_seconds())}},
        sort=[('next_check_at', 1)], return_document=ReturnDocument.AFTER)


def flush_notification(alert):
    pending = alert.get('pending_notification')
    if not pending:
        return
    selector = {'_id': alert['_id'], 'user_id': alert['user_id'], 'revision': alert['revision']}
    if not store('price_alerts').find_one({**selector, 'enabled': True}):
        return
    identifier = pending['id']
    fields = {key: value for key, value in pending.items() if key != 'id'}
    store('price_notifications').update_one({'_id': identifier, 'user_id': alert['user_id']},
        {'$setOnInsert': fields}, upsert=True)
    store('price_alerts').update_one({**selector, 'pending_notification.id': identifier},
        {'$unset': {'pending_notification': ''}})


def check_claimed(alert):
    # Persist a pending notification with the observed price before publishing it.
    # If the database fails mid-delivery, the next check can safely retry the upsert.
    flush_notification(alert)
    timestamp = now()
    selector = {'_id': alert['_id'], 'user_id': alert['user_id'], 'enabled': True, 'revision': alert['revision']}
    try:
        amount = observe_price(alert)
    except (ValueError, ShoppingError) as error:
        message = str(error) if isinstance(error, ValueError) else 'The shopping provider is unavailable. A later check will retry.'
        store('price_alerts').update_one(selector, {'$set': {'status': 'unavailable', 'message': message,
                                                          'last_checked_at': timestamp}})
        return
    dropped = amount < alert['min_price'] and amount <= alert['target_price']
    fields = {'status': 'price_drop' if dropped else 'checked', 'message': None,
              'current_price': amount, 'min_price': min(amount, alert['min_price']), 'last_checked_at': timestamp}
    if dropped:
        fields['pending_notification'] = {
            'id': sha256(f"{alert['_id']}:{alert['revision']}:{amount}".encode()).hexdigest(),
            'alert_id': alert['_id'], 'title': alert['product']['title'], 'source': alert['source'],
            'currency': alert['currency'], 'previous_price': alert['baseline_price'], 'price': amount,
            'url': alert['product'].get('url'), 'read': False, 'updated_at': timestamp,
        }
    result = store('price_alerts').update_one(selector, {'$set': fields})
    if dropped and result.matched_count:
        flush_notification({**alert, 'pending_notification': fields['pending_notification']})


@router.post('/api/price-alerts/{identifier}/check')
def check_alert(identifier: str, session=Depends(require_session)):
    user = session['sub']
    row = owned('price_alerts', identifier, user)
    if not row['enabled']:
        raise HTTPException(409, 'Resume this alert before checking it.')
    claimed = claim_due(identifier, user)
    if claimed is None:
        raise HTTPException(429, 'This alert has already been checked. Wait until the next scheduled check.')
    check_claimed(claimed)
    return public_alert(owned('price_alerts', identifier, user))


@router.get('/api/notifications')
def list_notifications(offset: int = Query(0, ge=0, le=100000), session=Depends(require_session)):
    rows = list(store('price_notifications').find({'user_id': session['sub']}).sort([('updated_at', -1), ('_id', 1)]).skip(offset).limit(51))
    return {'items': [{'id': row['_id'], 'title': row['title'], 'currency': row['currency'],
                      'previousPrice': row['previous_price'], 'price': row['price'], 'read': row['read'],
                      'url': row.get('url'), 'createdAt': iso(row['updated_at'])} for row in rows[:50]], 'hasMore': len(rows) > 50}


@router.patch('/api/notifications/{identifier}/read')
def read_notification(identifier: str, session=Depends(require_session)):
    store('price_notifications').update_one({'_id': identifier, 'user_id': session['sub']}, {'$set': {'read': True}})
    return {'ok': True}


def run_due_checks(max_checks=100, stop=None):
    count = 0
    for _ in range(max_checks):
        if stop is not None and stop.is_set():
            break
        try:
            alert = claim_due()
            if alert is None:
                break
            check_claimed(alert)
            count += 1
        except (PyMongoError, OSError):
            logger.warning('Price alert check failed; the next scheduled cycle will retry')
            break
    return count


def worker_loop(stop: Event):
    while not stop.is_set():
        run_due_checks(stop=stop)
        stop.wait(60)

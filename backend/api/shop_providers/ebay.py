"""eBay Browse API keyword search (free with an eBay developer account).

Docs: https://developer.ebay.com/api-docs/buy/browse/resources/item_summary/methods/search
Auth: client-credentials application token, valid for two hours. eBay allows
1,000 token requests a day, so the token is cached and reused until shortly
before it expires.
"""
import base64
import os
from threading import Lock
from time import monotonic

import requests

from api.shop_providers.base import DailyBudget, ProviderError, get_json, product

NAME = 'ebay'
LABEL = 'eBay'
SEARCH_URL = 'https://api.ebay.com/buy/browse/v1/item_summary/search'
TOKEN_URL = 'https://api.ebay.com/identity/v1/oauth2/token'
SCOPE = 'https://api.ebay.com/oauth/api_scope'

budget = DailyBudget('EBAY_DAILY_CALLS', 4000)
_token_lock = Lock()
_token = None  # (access_token, expires_at_monotonic, credentials_fingerprint)


def credentials():
    return os.environ.get('EBAY_CLIENT_ID', '').strip(), os.environ.get('EBAY_CLIENT_SECRET', '').strip()


def configured():
    client_id, secret = credentials()
    return bool(client_id and secret)


def marketplace():
    return os.environ.get('EBAY_MARKETPLACE_ID', 'EBAY_US').strip() or 'EBAY_US'


def access_token():
    global _token
    client_id, secret = credentials()
    fingerprint = hash((client_id, secret))
    with _token_lock:
        if _token and _token[2] == fingerprint and monotonic() < _token[1]:
            return _token[0]
        basic = base64.b64encode(f'{client_id}:{secret}'.encode()).decode()
        try:
            response = requests.post(TOKEN_URL, timeout=(5, 10), allow_redirects=False,
                                     headers={'Authorization': f'Basic {basic}',
                                              'Content-Type': 'application/x-www-form-urlencoded'},
                                     data={'grant_type': 'client_credentials', 'scope': SCOPE})
        except requests.RequestException:
            raise ProviderError('Cannot reach eBay sign-in right now.', 'unavailable') from None
        with response:
            if response.status_code in (400, 401):
                raise ProviderError('eBay rejected the configured credentials.', 'auth')
            if response.status_code != 200:
                raise ProviderError('eBay sign-in is unavailable right now.', 'unavailable')
            try:
                payload = response.json()
                token, lifetime = payload['access_token'], int(payload['expires_in'])
            except (ValueError, KeyError, TypeError):
                raise ProviderError('eBay returned an invalid sign-in response.', 'invalid_response') from None
        # Refresh five minutes early so a request never uses an expiring token.
        _token = (token, monotonic() + max(60, lifetime - 300), fingerprint)
        return token


def to_product(item):
    if not isinstance(item, dict):
        return None
    price = item.get('price') if isinstance(item.get('price'), dict) else {}
    image = (item.get('image') or {}).get('imageUrl') if isinstance(item.get('image'), dict) else None
    if not image and isinstance(item.get('thumbnailImages'), list) and item['thumbnailImages']:
        first = item['thumbnailImages'][0]
        image = first.get('imageUrl') if isinstance(first, dict) else None
    categories = item.get('categories') if isinstance(item.get('categories'), list) else []
    category = next((c.get('categoryName') for c in categories if isinstance(c, dict) and c.get('categoryName')), None)
    seller = item.get('seller') if isinstance(item.get('seller'), dict) else {}
    attributes = [item.get('condition')]
    if seller.get('username'):
        attributes.append(f"Seller: {seller['username']}")
    return product(provider=NAME, merchant=LABEL, identity=item.get('itemId'), title=item.get('title'),
                   description=item.get('shortDescription'), price=price.get('value'),
                   currency=price.get('currency'), image=image,
                   url=item.get('itemAffiliateWebUrl') or item.get('itemWebUrl'),
                   category=category, attributes=[a for a in attributes if isinstance(a, str)])


def search(query, limit):
    if not budget.take():
        raise ProviderError('eBay daily search limit reached. Try again tomorrow.', 'quota')
    payload = get_json(SEARCH_URL, LABEL, params={'q': query, 'limit': str(max(1, min(limit, 50)))},
                       headers={'Authorization': f'Bearer {access_token()}',
                                'X-EBAY-C-MARKETPLACE-ID': marketplace()})
    items = payload.get('itemSummaries', [])
    if not isinstance(items, list):
        raise ProviderError('eBay returned an invalid response.', 'invalid_response')
    return [result for result in map(to_product, items) if result]

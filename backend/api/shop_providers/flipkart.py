"""Flipkart Affiliate API keyword search (free for Flipkart affiliates).

Docs: https://affiliate.flipkart.com/api-docs/af_prod_ref.html
Returns at most 10 products per search.
"""
import json
import os

from api.shop_providers.base import DailyBudget, ProviderError, get_json, product

NAME = 'flipkart'
LABEL = 'Flipkart'
SEARCH_URL = 'https://affiliate-api.flipkart.net/affiliate/1.0/search.json'
MAX_RESULTS = 10

budget = DailyBudget('FLIPKART_DAILY_CALLS', 5000)


def credentials():
    return (os.environ.get('FLIPKART_AFFILIATE_ID', '').strip(),
            os.environ.get('FLIPKART_AFFILIATE_TOKEN', '').strip())


def configured():
    affiliate, token = credentials()
    return bool(affiliate and token)


def price_of(info):
    # Special price includes extra offers; selling price is the listed price.
    for key in ('flipkartSpecialPrice', 'flipkartSellingPrice', 'maximumRetailPrice'):
        value = info.get(key)
        if isinstance(value, dict) and value.get('amount') is not None:
            return value.get('amount'), value.get('currency')
    return None, None


def image_of(urls):
    if not isinstance(urls, dict):
        return None
    for size in ('400x400', '800x800', '200x200'):
        if urls.get(size):
            return urls[size]
    return next((value for value in urls.values() if isinstance(value, str)), None)


def category_of(path):
    """categoryPath is a JSON string of nested node lists; use the deepest name."""
    try:
        nodes = json.loads(path) if isinstance(path, str) else path
        while isinstance(nodes, list) and nodes and isinstance(nodes[0], list):
            nodes = nodes[0]
        names = [node.get('node_name') for node in nodes if isinstance(node, dict) and node.get('node_name')]
        names = [name for name in names if name != 'FLIPKART_TREE']
        return names[-1] if names else None
    except (ValueError, TypeError):
        return None


def to_product(row):
    info = row.get('productBaseInfoV1') if isinstance(row, dict) else None
    if not isinstance(info, dict):
        return None
    amount, currency = price_of(info)
    details = info.get('attributes') if isinstance(info.get('attributes'), dict) else {}
    attributes = [f'{key.capitalize()}: {value}' for key, value in details.items()
                  if key in ('color', 'size', 'storage', 'displaySize') and isinstance(value, str) and value]
    shipping = row.get('productShippingInfoV1') if isinstance(row.get('productShippingInfoV1'), dict) else {}
    if isinstance(shipping.get('sellerName'), str) and shipping['sellerName']:
        attributes.append(f"Seller: {shipping['sellerName']}")
    return product(provider=NAME, merchant=LABEL, identity=info.get('productId'), title=info.get('title'),
                   description=info.get('productDescription'), price=amount, currency=currency or 'INR',
                   image=image_of(info.get('imageUrls')), url=info.get('productUrl'),
                   brand=info.get('productBrand'), category=category_of(info.get('categoryPath')),
                   in_stock=info.get('inStock'), attributes=attributes)


def search(query, limit):
    if not budget.take():
        raise ProviderError('Flipkart daily search limit reached. Try again tomorrow.', 'quota')
    affiliate, token = credentials()
    payload = get_json(SEARCH_URL, LABEL,
                       params={'query': query, 'resultCount': str(max(1, min(limit, MAX_RESULTS)))},
                       headers={'Fk-Affiliate-Id': affiliate, 'Fk-Affiliate-Token': token})
    rows = payload.get('productInfoList', [])
    if not isinstance(rows, list):
        raise ProviderError('Flipkart returned an invalid response.', 'invalid_response')
    return [result for result in map(to_product, rows) if result]

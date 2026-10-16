"""Live products are fetched on demand; credentials stay on the backend."""
import os
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urlparse
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

POOL = ThreadPoolExecutor(max_workers=4)
AMAZON_LOCK = Lock()
AMAZON_CLIENT = None


def required(names):
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        raise ValueError('Configure backend settings: ' + ', '.join(missing))
    return [os.environ[name] for name in names]


def safe_url(url):
    return url if isinstance(url, str) and urlparse(url).scheme in ('http', 'https') else None


def product(source, identifier, title, brand='', description='', price=None, currency=None, url=None):
    return dict(id=f'{source}:{identifier}', title=title, brand=brand, description=description,
                representation_text=f'[Brand] {brand} | [Title] {title} | [Details] {description}',
                price=price, currency=currency, productUrl=safe_url(url), marketplace=source,
                matchSources=['marketplace'])


def amazon(query):
    global AMAZON_CLIENT
    credential, secret, version, partner = required([
        'AMAZON_CREDENTIAL_ID', 'AMAZON_CREDENTIAL_SECRET',
        'AMAZON_CREDENTIAL_VERSION', 'AMAZON_PARTNER_TAG'])
    sdk = Path(__file__).resolve().parents[2] / 'vendor/creatorsapi-python-sdk'
    if str(sdk) not in sys.path:
        sys.path.insert(0, str(sdk))
    try:
        from creatorsapi_python_sdk.api_client import ApiClient
        from creatorsapi_python_sdk.api.default_api import DefaultApi
        from creatorsapi_python_sdk.models.search_items_request_content import SearchItemsRequestContent
    except ImportError:
        raise ValueError('Install the official Amazon SDK: run scripts/install_amazon_sdk.py.') from None
    # The official SDK owns token caching and refresh; serialize access to its client.
    with AMAZON_LOCK:
        if AMAZON_CLIENT is None:
            AMAZON_CLIENT = ApiClient(credential_id=credential, credential_secret=secret, version=version)
        request = SearchItemsRequestContent(
            partner_tag=partner, keywords=query, search_index='All', item_count=10,
            resources=['itemInfo.title', 'itemInfo.byLineInfo', 'itemInfo.features',
                       'offersV2.listings.price'])
        response = DefaultApi(AMAZON_CLIENT).search_items(
            x_marketplace=os.getenv('AMAZON_MARKETPLACE', 'www.amazon.in'),
            search_items_request_content=request, _request_timeout=(5.0, 10.0))
        data = response.to_dict()
    if data.get('errors') and not (data.get('searchResult') or {}).get('items'):
        raise RuntimeError('Amazon returned API errors; check account access and marketplace settings.')
    products = []
    for item in (data.get('searchResult') or {}).get('items', []):
        info = item.get('itemInfo') or {}
        title = (info.get('title') or {}).get('displayValue', '')
        brand = ((info.get('byLineInfo') or {}).get('brand') or {}).get('displayValue', '')
        features = (info.get('features') or {}).get('displayValues') or []
        listings = (item.get('offersV2') or {}).get('listings') or []
        price = (listings[0].get('price') or {}) if listings else {}
        money = price.get('money') or price
        if item.get('asin') and title:
            products.append(product('amazon', item['asin'], title, brand, ' | '.join(features),
                                    money.get('amount'), money.get('currency'), item.get('detailPageURL')))
    return products


def flipkart(query):
    tracking, token = required(['FLIPKART_AFFILIATE_ID', 'FLIPKART_AFFILIATE_TOKEN'])
    url = 'https://affiliate-api.flipkart.net/affiliate/1.0/search.json?' + urlencode({'query': query, 'resultCount': 10})
    request = Request(url, headers={'Fk-Affiliate-Id': tracking, 'Fk-Affiliate-Token': token})
    with urlopen(request, timeout=10) as response:
        data = json.load(response)
    products = []
    for item in data.get('productInfoList', []):
        info = item.get('productBaseInfoV1') or {}
        if not info:
            base = item.get('productBaseInfo') or {}
            info = {**(base.get('productAttributes') or {}),
                    'productId': (base.get('productIdentifier') or {}).get('productId')}
        price = info.get('flipkartSellingPrice') or info.get('sellingPrice') or {}
        if info.get('productId') and info.get('title'):
            products.append(product('flipkart', info['productId'], info['title'],
                                    info.get('productBrand', ''), info.get('productDescription') or '',
                                    price.get('amount'), price.get('currency'), info.get('productUrl')))
    return products


def live_search(query, sources):
    jobs = {name: POOL.submit({'amazon': amazon, 'flipkart': flipkart}[name], query)
            for name in sources}
    products, statuses = [], {}
    for name, job in jobs.items():
        try:
            results = job.result(timeout=20)
            products.extend(results)
            statuses[name] = {'status': 'ok', 'count': len(results)}
        except ValueError as error:
            statuses[name] = {'status': 'unavailable', 'message': str(error)}
        except Exception:
            # SDK exception bodies can contain request information; never expose them.
            statuses[name] = {'status': 'error', 'message': f'{name.title()} search failed or timed out. Check API access and credentials.'}
    return products, statuses

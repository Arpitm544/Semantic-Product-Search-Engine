"""Independent Shopify and WooCommerce stores: config, mapping, robots.txt, and search.

HTTP is replaced with stand-in responses shaped like Shopify's public
/products.json and the WooCommerce Store API.
"""
from unittest.mock import MagicMock, patch

import pytest

from api.shop_providers import base, enabled_providers, stores
from api.shop_providers.base import ProviderError
from api.shop_providers.stores import StoreConfig, StoreProvider, parse_stores

SHOPIFY = StoreConfig('shopify', 'www.example-store.in', 'INR')
WOO = StoreConfig('woocommerce', 'shop.example.com', 'INR')

SHOPIFY_ROW = {
    'id': 7012345678901, 'title': 'Cotton Oversized T-Shirt &amp; Tote', 'handle': 'cotton-oversized-tee',
    'body_html': '<p>Soft <strong>100% cotton</strong> tee.</p>', 'vendor': 'Bewild', 'product_type': 'T-Shirts',
    'tags': ['cotton', 'summer'],
    'variants': [{'price': '799.00', 'available': False}, {'price': '699.00', 'available': True}],
    'images': [{'src': 'https://cdn.shopify.com/s/files/1/tee.jpg'}],
}
WOO_ROW = {
    'id': 4321, 'name': 'Handmade Leather Wallet', 'permalink': 'https://shop.example.com/product/leather-wallet/',
    'short_description': '<p>Full-grain leather.</p>', 'is_in_stock': True,
    'prices': {'price': '149900', 'currency_code': 'INR', 'currency_minor_unit': 2},
    'images': [{'src': 'https://shop.example.com/wp-content/uploads/wallet.jpg'}],
    'categories': [{'name': 'Accessories'}], 'brands': [{'name': 'Kraft &amp; Co'}],
}


def response(status=200, payload=None, text=''):
    value = MagicMock(status_code=status, text=text)
    value.json.return_value = payload
    value.__enter__.return_value = value
    value.__exit__.return_value = False
    return value


def robots(text='User-agent: *\nDisallow: /admin\nDisallow: /search\n', status=200):
    return patch.object(stores, 'fetch_robots', return_value=(status, text if status == 200 else ''))


def test_robots_txt_is_downloaded_from_the_store_with_our_user_agent():
    with patch.object(stores.requests, 'get', return_value=response(200, text='User-agent: *\nAllow: /\n')) as get:
        assert stores.fetch_robots('shop.example.com') == (200, 'User-agent: *\nAllow: /\n')
    assert get.call_args.args[0] == 'https://shop.example.com/robots.txt'
    assert get.call_args.kwargs['headers'] == {'User-Agent': stores.USER_AGENT}
    assert get.call_args.kwargs['allow_redirects'] is False


@pytest.fixture(autouse=True)
def no_store_env(monkeypatch):
    for name in ('SHOP_STORES', 'SHOP_STORE_MAX_PRODUCTS', 'SHOP_STORE_DAILY_CALLS',
                 'EBAY_CLIENT_ID', 'EBAY_CLIENT_SECRET'):
        monkeypatch.delenv(name, raising=False)
    stores._providers.clear()


# --- Configuration -------------------------------------------------------

def test_store_list_is_parsed_with_default_currency():
    parsed, errors = parse_stores(' shopify:WWW.Example-Store.in:inr , woocommerce:shop.example.com ')
    assert parsed == [SHOPIFY, WOO] and errors == []


@pytest.mark.parametrize('entry', [
    'magento:shop.example.com', 'shopify:localhost', 'shopify:127.0.0.1', 'shopify:shop.example.com:8080',
    'shopify:https', 'shopify:shop.example.com/products', 'shopify:shop.example.com:RUPEES', 'shopify:', 'shopify:a.b:INR:x',
])
def test_unsafe_or_malformed_entries_are_rejected(entry):
    parsed, errors = parse_stores(entry)
    assert parsed == [] and errors == [entry]


def test_duplicates_are_dropped_and_store_count_is_capped():
    entries = ','.join(f'shopify:store{i}.example.com' for i in range(25)) + ',shopify:store0.example.com'
    parsed, errors = parse_stores(entries)
    assert len(parsed) == stores.MAX_STORES and len(errors) == 5


def test_configured_stores_are_enabled_and_reused(monkeypatch):
    monkeypatch.setenv('SHOP_STORES', 'shopify:www.example-store.in, bad-entry')
    first = enabled_providers()
    assert [p.NAME for p in first] == ['store:www.example-store.in']
    assert enabled_providers()[0] is first[0]


# --- Mapping ---------------------------------------------------------------

def test_shopify_product_maps_cheapest_variant_availability_and_link():
    result = stores.shopify_product(SHOPIFY, SHOPIFY_ROW)
    assert result['id'] == 'store:www.example-store.in:7012345678901'
    assert result['title'] == 'Cotton Oversized T-Shirt & Tote'
    assert result['description'] == 'Soft 100% cotton tee.'
    assert result['price'] == 699.0 and result['currency'] == 'INR' and result['inStock'] is True
    assert result['url'] == 'https://www.example-store.in/products/cotton-oversized-tee'
    assert result['brand'] == 'Bewild' and result['category'] == 'T-Shirts'
    assert result['merchant'] == 'www.example-store.in' and result['matchSources'] == ['store']


def test_woocommerce_product_converts_minor_units_and_entities():
    result = stores.woocommerce_product(WOO, WOO_ROW)
    assert result['price'] == 1499.0 and result['currency'] == 'INR'
    assert result['brand'] == 'Kraft & Co' and result['category'] == 'Accessories'
    assert result['url'] == 'https://shop.example.com/product/leather-wallet/'
    assert result['description'] == 'Full-grain leather.' and result['inStock'] is True


# --- Searching -------------------------------------------------------------

def test_shopify_store_downloads_catalog_once_and_searches_by_keyword():
    other = {**SHOPIFY_ROW, 'id': 2, 'title': 'Denim Jacket', 'handle': 'denim', 'tags': [], 'body_html': '',
             'product_type': 'Jackets'}
    provider = StoreProvider(SHOPIFY)
    with robots(), patch.object(base.requests, 'get', return_value=response(payload={'products': [SHOPIFY_ROW, other]})) as get:
        assert [p['title'] for p in provider.search('cotton tee', 10)] == ['Cotton Oversized T-Shirt & Tote']
        assert [p['title'] for p in provider.search('denim jacket', 10)] == ['Denim Jacket']
    assert get.call_count == 1
    assert get.call_args.args[0] == 'https://www.example-store.in/products.json'
    assert get.call_args.kwargs['params'] == {'limit': '250', 'page': '1'}
    assert get.call_args.kwargs['headers']['User-Agent'] == stores.USER_AGENT


def test_shopify_catalog_pages_until_short_page_or_cap(monkeypatch):
    monkeypatch.setenv('SHOP_STORE_MAX_PRODUCTS', '300')
    full = [{**SHOPIFY_ROW, 'id': i, 'handle': f'p{i}'} for i in range(250)]
    pages = [response(payload={'products': full}), response(payload={'products': full})]
    with robots(), patch.object(base.requests, 'get', side_effect=pages) as get:
        StoreProvider(SHOPIFY).search('cotton', 5)
    assert [call.kwargs['params']['page'] for call in get.call_args_list] == ['1', '2']


def test_woocommerce_store_searches_live_store_api():
    provider = StoreProvider(WOO)
    with robots(), patch.object(base.requests, 'get', return_value=response(payload=[WOO_ROW])) as get:
        results = provider.search('leather wallet', 10)
    assert [r['title'] for r in results] == ['Handmade Leather Wallet']
    assert get.call_args.args[0] == 'https://shop.example.com/wp-json/wc/store/v1/products'
    assert get.call_args.kwargs['params'] == {'search': 'leather wallet', 'per_page': '10'}


def test_robots_txt_disallow_is_respected():
    provider = StoreProvider(SHOPIFY)
    with robots('User-agent: *\nDisallow: /products.json\n'), patch.object(base.requests, 'get') as get:
        with pytest.raises(ProviderError) as error:
            provider.search('tee', 10)
    assert error.value.code == 'blocked' and 'robots.txt' in str(error.value)
    get.assert_not_called()


def test_forbidden_robots_txt_blocks_and_missing_robots_txt_allows():
    with robots(status=403), patch.object(base.requests, 'get') as get:
        with pytest.raises(ProviderError, match='robots'):
            StoreProvider(WOO).search('wallet', 5)
        get.assert_not_called()
    with robots(status=404), patch.object(base.requests, 'get', return_value=response(payload=[WOO_ROW])):
        assert StoreProvider(WOO).search('wallet', 5)


def test_redirecting_store_asks_for_its_final_address():
    with robots(), patch.object(base.requests, 'get', return_value=response(301)):
        with pytest.raises(ProviderError) as error:
            StoreProvider(WOO).search('wallet', 5)
    assert error.value.code == 'redirect'


def test_store_daily_request_cap(monkeypatch):
    monkeypatch.setenv('SHOP_STORE_DAILY_CALLS', '1')
    provider = StoreProvider(WOO)
    with robots(), patch.object(base.requests, 'get', return_value=response(payload=[WOO_ROW])) as get:
        provider.search('wallet', 5)
        with pytest.raises(ProviderError) as error:
            provider.search('belt', 5)
    assert error.value.code == 'quota' and get.call_count == 1


def test_stores_join_the_online_shops_search(monkeypatch):
    from api import shops_service
    shops_service._cache.clear()
    monkeypatch.setenv('SHOP_STORES', 'woocommerce:shop.example.com')
    with robots(), patch.object(base.requests, 'get', return_value=response(payload=[WOO_ROW])):
        result = shops_service.search_shops('leather wallet')
    shops_service._cache.clear()
    assert result['providers'] == [{'name': 'store:shop.example.com', 'label': 'shop.example.com',
                                    'status': 'ok', 'count': 1, 'cached': False}]
    assert result['results'][0]['merchant'] == 'shop.example.com'


def test_filler_words_do_not_match_unrelated_store_products():
    assert stores.keyword_query('wireless earbuds with noise cancellation') == 'wireless earbuds noise cancellation'
    assert stores.keyword_query('with the') == 'with the'
    sunscreen = {**SHOPIFY_ROW, 'id': 3, 'handle': 'sunscreen', 'title': 'Sunscreen With Vitamin C',
                 'body_html': '<p>Glow with every use.</p>', 'tags': [], 'product_type': 'Skin'}
    earbuds = {**SHOPIFY_ROW, 'id': 4, 'handle': 'buds', 'title': 'Wireless Earbuds', 'tags': [],
               'body_html': '', 'product_type': 'Audio'}
    provider = StoreProvider(SHOPIFY)
    with robots(), patch.object(base.requests, 'get', return_value=response(payload={'products': [sunscreen, earbuds]})):
        titles = [p['title'] for p in provider.search('earbuds with noise cancellation', 10)]
    assert titles == ['Wireless Earbuds']


def test_shopify_pagination_stops_when_page_adds_no_new_products():
    repeated = [{**SHOPIFY_ROW, 'id': i + 1, 'handle': f'item-{i}'} for i in range(stores.SHOPIFY_PAGE_SIZE)]
    provider = StoreProvider(SHOPIFY)
    with robots(), patch.object(base.requests, 'get', return_value=response(payload={'products': repeated})) as get:
        provider.search('cotton', 5)
    assert get.call_count == 2

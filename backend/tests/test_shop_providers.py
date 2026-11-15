"""Free online-shop search: provider adapters, parallel merging, and the API route.

Every network call is replaced with a stand-in response shaped like the
providers' documented APIs, so these tests never need real keys or quota.
"""
import base64
from threading import Event
from unittest.mock import MagicMock, patch

import pytest
import requests
from fastapi.testclient import TestClient

from api import shops_service
from api.shop_providers import base, ebay, stores
from api.shop_providers.base import DailyBudget, ProviderError
from api.shopping_service import ShoppingError

# Shapes follow eBay's Browse API spec (ItemSummary) and Shopify's public /products.json.
EBAY_ITEM = {
    'itemId': 'v1|1234567890|0', 'title': 'Sony WH-1000XM5 Wireless Headphones',
    'price': {'value': '279.99', 'currency': 'USD'},
    'image': {'imageUrl': 'https://i.ebayimg.com/images/g/abc/s-l225.jpg'},
    'itemWebUrl': 'https://www.ebay.com/itm/1234567890',
    'seller': {'username': 'audio_outlet', 'feedbackPercentage': '99.5'},
    'condition': 'New', 'categories': [{'categoryId': '112529', 'categoryName': 'Headphones'}],
    'shortDescription': 'Industry-leading noise cancelling.',
}
# An independent Shopify store's product: it reports brand, INR price, and stock.
STORE_PRODUCT = stores.shopify_product(stores.StoreConfig('shopify', 'www.example-store.in', 'INR'), {
    'id': 7001, 'title': 'Sony WH-1000XM5 Bluetooth Headset', 'handle': 'sony-wh-1000xm5',
    'body_html': '<p>Noise cancelling headphones.</p>', 'vendor': 'Sony', 'product_type': 'Headphones',
    'variants': [{'price': '24990.00', 'available': True}],
    'images': [{'src': 'https://cdn.shopify.com/s/files/1/sony.jpg'}],
})


def response(status=200, payload=None):
    value = MagicMock(status_code=status)
    value.json.return_value = payload if payload is not None else {}
    value.__enter__.return_value = value
    value.__exit__.return_value = False
    return value


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    for name in ('EBAY_CLIENT_ID', 'EBAY_CLIENT_SECRET', 'EBAY_DAILY_CALLS', 'EBAY_MARKETPLACE_ID', 'SHOP_STORES'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(ebay, '_token', None)
    monkeypatch.setattr(ebay, 'budget', DailyBudget('EBAY_DAILY_CALLS', 4000))
    shops_service._cache.clear()
    yield
    shops_service._cache.clear()


def enable_ebay(monkeypatch):
    monkeypatch.setenv('EBAY_CLIENT_ID', 'client-id')
    monkeypatch.setenv('EBAY_CLIENT_SECRET', 'client-secret')


# --- eBay -----------------------------------------------------------------

def test_ebay_item_maps_to_shared_result_shape():
    result = ebay.to_product(EBAY_ITEM)
    assert result['id'] == 'ebay:v1|1234567890|0' and result['merchant'] == 'eBay'
    assert result['price'] == 279.99 and result['currency'] == 'USD'
    assert result['url'] == 'https://www.ebay.com/itm/1234567890'
    assert result['imageUrl'].startswith('https://i.ebayimg.com/')
    assert result['category'] == 'Headphones' and result['matchSources'] == ['ebay']
    assert result['attributes'] == ['New', 'Seller: audio_outlet']


def test_ebay_prefers_affiliate_link_and_rejects_unsafe_urls():
    result = ebay.to_product({**EBAY_ITEM, 'itemAffiliateWebUrl': 'https://www.ebay.com/itm/1?campid=1',
                              'image': {'imageUrl': 'javascript:alert(1)'}})
    assert result['url'].endswith('campid=1') and result['imageUrl'] is None
    assert ebay.to_product({'itemId': '1'}) is None and ebay.to_product('junk') is None


def test_ebay_search_mints_one_token_and_reuses_it(monkeypatch):
    enable_ebay(monkeypatch)
    token = response(payload={'access_token': 'app-token', 'expires_in': 7200, 'token_type': 'Application Access Token'})
    with patch.object(ebay.requests, 'post', return_value=token) as post, \
            patch.object(base.requests, 'get', return_value=response(payload={'itemSummaries': [EBAY_ITEM]})) as get:
        assert ebay.search('headphones', 10)[0]['title'].startswith('Sony')
        ebay.search('speakers', 10)
    post.assert_called_once()
    kwargs = post.call_args.kwargs
    assert post.call_args.args[0] == 'https://api.ebay.com/identity/v1/oauth2/token'
    assert kwargs['headers']['Authorization'] == 'Basic ' + base64.b64encode(b'client-id:client-secret').decode()
    assert kwargs['data'] == {'grant_type': 'client_credentials', 'scope': 'https://api.ebay.com/oauth/api_scope'}
    search_kwargs = get.call_args.kwargs
    assert get.call_args.args[0] == 'https://api.ebay.com/buy/browse/v1/item_summary/search'
    assert search_kwargs['params'] == {'q': 'speakers', 'limit': '10'}
    assert search_kwargs['headers'] == {'Authorization': 'Bearer app-token', 'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US'}


def test_ebay_rejected_credentials_are_reported_without_secrets(monkeypatch):
    enable_ebay(monkeypatch)
    with patch.object(ebay.requests, 'post', return_value=response(401)):
        with pytest.raises(ProviderError) as error:
            ebay.search('headphones', 10)
    assert error.value.code == 'auth' and 'client-secret' not in str(error.value)


# --- Shared HTTP handling and budgets ------------------------------------

@pytest.mark.parametrize('status,code', [(401, 'auth'), (403, 'auth'), (429, 'quota'), (500, 'unavailable'), (410, 'unavailable')])
def test_provider_http_errors_are_sanitized(status, code):
    with patch.object(base.requests, 'get', return_value=response(status)):
        with pytest.raises(ProviderError) as error:
            base.get_json('https://example.test', 'Shop')
    assert error.value.code == code


def test_provider_timeout_and_invalid_json_are_sanitized():
    with patch.object(base.requests, 'get', side_effect=requests.Timeout):
        with pytest.raises(ProviderError, match='too long'):
            base.get_json('https://example.test', 'Shop')
    bad = response()
    bad.json.side_effect = ValueError
    with patch.object(base.requests, 'get', return_value=bad):
        with pytest.raises(ProviderError, match='invalid'):
            base.get_json('https://example.test', 'Shop')


def test_daily_budget_stops_calls_before_reaching_the_provider(monkeypatch):
    enable_ebay(monkeypatch)
    monkeypatch.setenv('EBAY_DAILY_CALLS', '1')
    token = response(payload={'access_token': 'app-token', 'expires_in': 7200})
    with patch.object(ebay.requests, 'post', return_value=token), \
            patch.object(base.requests, 'get', return_value=response(payload={'itemSummaries': []})) as get:
        ebay.search('one', 10)
        with pytest.raises(ProviderError) as error:
            ebay.search('two', 10)
    assert error.value.code == 'quota' and get.call_count == 1


# --- Parallel search across shops ----------------------------------------

def fake_provider(name, results=None, error=None, wait_for=None):
    provider = MagicMock()
    provider.NAME, provider.LABEL = name, name.capitalize()

    def search(query, limit):
        if wait_for is not None:
            wait_for.wait(5)
        if error:
            raise error
        return results or []
    provider.search.side_effect = search
    return provider


def item(provider, index):
    return {'id': f'{provider}:{index}', 'title': f'{provider} {index}', 'matchSources': [provider]}


def test_no_configured_shop_is_a_clear_setup_error():
    with patch.object(shops_service, 'enabled_providers', return_value=[]):
        with pytest.raises(ShoppingError) as error:
            shops_service.search_shops('headphones')
    assert error.value.code == 'shops_not_configured' and error.value.status == 503


def test_results_from_all_shops_are_interleaved():
    shops = [fake_provider('ebay', [item('ebay', i) for i in range(3)]),
             fake_provider('store', [item('store', i) for i in range(2)])]
    with patch.object(shops_service, 'enabled_providers', return_value=shops):
        result = shops_service.search_shops('headphones')
    assert [r['id'] for r in result['results']] == ['ebay:0', 'store:0', 'ebay:1', 'store:1', 'ebay:2']
    assert [p['status'] for p in result['providers']] == ['ok', 'ok'] and 'warning' not in result


def test_one_failing_shop_does_not_hide_the_others():
    shops = [fake_provider('ebay', error=ProviderError('eBay rejected the configured credentials.', 'auth')),
             fake_provider('store', [item('store', 0)])]
    with patch.object(shops_service, 'enabled_providers', return_value=shops):
        result = shops_service.search_shops('headphones')
    assert [r['id'] for r in result['results']] == ['store:0']
    assert result['providers'][0] == {'name': 'ebay', 'label': 'Ebay', 'status': 'auth',
                                      'message': 'eBay rejected the configured credentials.', 'count': 0}
    assert 'Ebay' in result['warning']


def test_all_shops_failing_is_a_service_error():
    shops = [fake_provider('ebay', error=ProviderError('down', 'unavailable')),
             fake_provider('store', error=RuntimeError('boom'))]
    with patch.object(shops_service, 'enabled_providers', return_value=shops):
        with pytest.raises(ShoppingError) as error:
            shops_service.search_shops('headphones')
    assert error.value.code == 'shops_unavailable'


def test_slow_shop_is_skipped_at_the_deadline(monkeypatch):
    release = Event()
    shops = [fake_provider('ebay', [item('ebay', 0)]), fake_provider('store', [item('store', 0)], wait_for=release)]
    monkeypatch.setattr(shops_service, 'DEADLINE_SECONDS', 0.2)
    try:
        with patch.object(shops_service, 'enabled_providers', return_value=shops):
            result = shops_service.search_shops('headphones')
    finally:
        release.set()
    assert [r['id'] for r in result['results']] == ['ebay:0']
    assert result['providers'][1]['status'] == 'timeout'


def test_repeat_searches_are_served_from_cache():
    shop = fake_provider('ebay', [item('ebay', 0)])
    with patch.object(shops_service, 'enabled_providers', return_value=[shop]):
        shops_service.search_shops('headphones')
        again = shops_service.search_shops('headphones')
    assert shop.search.call_count == 1 and again['providers'][0]['cached'] is True


def test_ranking_falls_back_to_shop_order_when_models_fail():
    payload = {'query': 'headphones', 'results': [item('ebay', 0)], 'warning': 'Results from www.example-store.in are unavailable right now.'}
    with patch.object(shops_service, 'get_candidate_ranker', side_effect=OSError('missing weights')):
        result = shops_service.rank_shops_response(payload)
    assert result['rankingStatus'] == 'unavailable' and result['results'] == payload['results']
    assert result['warning'].startswith('Results from www.example-store.in') and "shops' original order" in result['warning']


# --- API route and account features --------------------------------------

@pytest.fixture
def client():
    from api.main import app
    from api.auth import require_session
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[require_session] = lambda: {'sub': 'alice'}
    with patch('api.main.remember_search', side_effect=lambda context, payload: payload):
        yield TestClient(app)
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def test_search_route_serves_shops_and_reports_setup_errors(client):
    payload = {'query': 'headphones', 'source': 'shops', 'results': [item('ebay', 0)], 'providers': []}
    with patch('api.main.search_shops', return_value=payload), patch('api.main.rank_shops_response', side_effect=lambda r: r):
        response = client.get('/api/search?q=headphones&source=shops')
    assert response.status_code == 200 and response.json()['results'][0]['id'] == 'ebay:0'
    error = ShoppingError('No online shops are configured.', 'shops_not_configured', 503)
    with patch('api.main.search_shops', side_effect=error):
        response = client.get('/api/search?q=headphones&source=shops')
    assert response.status_code == 503 and response.json()['code'] == 'shops_not_configured'
    assert response.json()['source'] == 'shops'


def test_shop_preferences_apply_budget_but_skip_brand():
    from api.account_features import Preferences
    from api.product_prices import apply_preferences
    rows = [{**ebay.to_product(EBAY_ITEM)}, {**STORE_PRODUCT}]
    prefs = Preferences(currency='INR', maxBudget=30000, brands=['Sony']).model_dump()
    result = apply_preferences({'results': rows}, prefs, 'shops')
    assert [r['id'] for r in result['results']] == [STORE_PRODUCT['id']]
    assert result['skippedPreferences'] == ['brands'] and 'online shop results' in result['warning']


def test_shop_results_can_be_saved_but_not_price_alerted():
    from api.saved_products import SaveProduct
    from api import price_alerts
    saved = SaveProduct(source='shops', identity=STORE_PRODUCT['id'], product=STORE_PRODUCT)
    assert saved.product.brand == 'Sony'
    quote, reason = price_alerts.eligibility({'source': 'shops', 'identity': saved.identity,
                                               'product': saved.product.model_dump(mode='json')})
    assert quote is None and 'not available yet' in reason


@pytest.mark.parametrize('source,env,expected', [('shops', None, 10), ('shops', '3', 3),
                                                  ('serpapi', None, 5), ('mongo', None, 30)])
def test_each_source_uses_its_own_per_minute_limit(monkeypatch, source, env, expected):
    from api import search_limits
    monkeypatch.delenv('SHOPS_SEARCHES_PER_MINUTE', raising=False)
    monkeypatch.delenv('SHOPPING_SEARCHES_PER_MINUTE', raising=False)
    monkeypatch.delenv('CATALOG_SEARCHES_PER_MINUTE', raising=False)
    if env:
        monkeypatch.setenv('SHOPS_SEARCHES_PER_MINUTE', env)
    store = MagicMock()
    store.find_one_and_update.return_value = {'count': 1}
    with patch.object(search_limits, 'collection', return_value=store):
        search_limits.check_search_rate('alice', source)
    assert store.find_one_and_update.call_args.args[0]['count'] == {'$lt': expected}


# --- Ranking the whole pool and dropping unrelated results ------------------

class ScoringRanker:
    """Stand-in for the real ranker: scores by whether the title has 'earbuds'."""

    def __init__(self):
        self.seen = []

    def rank(self, query, products):
        self.seen = list(products)
        scored = [{**p, 'rerankerScore': 8.0 if 'earbuds' in p['title'] else -11.0, 'semanticScore': 0.0}
                  for p in products]
        return sorted(scored, key=lambda p: -p['rerankerScore'])


def shop_items(shop, titles):
    return [{'id': f'{shop}:{i}', 'title': title, 'matchSources': [shop]} for i, title in enumerate(titles)]


def test_models_rank_every_shops_candidates_before_the_cut():
    boat = fake_provider('boat', shop_items('boat', [f'earbuds model {i}' for i in range(10)]))
    others = [fake_provider(f'shop{n}', shop_items(f'shop{n}', [f'sweater {i}' for i in range(10)])) for n in range(7)]
    ranker = ScoringRanker()
    with patch.object(shops_service, 'enabled_providers', return_value=[boat, *others]), \
            patch.object(shops_service, 'get_candidate_ranker', return_value=ranker):
        result = shops_service.rank_shops_response(shops_service.search_shops('wireless earbuds'))
    assert len(ranker.seen) == 80  # every candidate from all 8 shops
    # All 10 relevant earbuds survive even though round-robin would give boat only 3 of 20 slots.
    assert [r['title'] for r in result['results']] == [f'earbuds model {i}' for i in range(10)]
    assert result['total'] == 10 and result['candidateCount'] == 80 and 'limit' not in result


def test_unrelated_results_are_kept_with_a_notice_when_nothing_is_relevant():
    shops = [fake_provider('shop1', shop_items('shop1', ['sweater', 'lip gloss']))]
    with patch.object(shops_service, 'enabled_providers', return_value=shops), \
            patch.object(shops_service, 'get_candidate_ranker', return_value=ScoringRanker()):
        result = shops_service.rank_shops_response(shops_service.search_shops('earbuds'))
    assert [r['title'] for r in result['results']] == ['sweater', 'lip gloss']
    assert result['warningCode'] == 'shops_no_close_match' and 'No close matches' in result['warning']


def test_relevant_results_have_no_close_match_notice():
    shops = [fake_provider('shop1', shop_items('shop1', ['wireless earbuds', 'sweater']))]
    with patch.object(shops_service, 'enabled_providers', return_value=shops), \
            patch.object(shops_service, 'get_candidate_ranker', return_value=ScoringRanker()):
        result = shops_service.rank_shops_response(shops_service.search_shops('earbuds'))
    assert [r['title'] for r in result['results']] == ['wireless earbuds'] and 'warning' not in result


def test_results_are_capped_at_the_limit_after_ranking():
    shops = [fake_provider(f'shop{n}', shop_items(f'shop{n}', [f'earbuds {n}-{i}' for i in range(10)])) for n in range(4)]
    with patch.object(shops_service, 'enabled_providers', return_value=shops), \
            patch.object(shops_service, 'get_candidate_ranker', return_value=ScoringRanker()):
        result = shops_service.rank_shops_response(shops_service.search_shops('earbuds'))
    assert len(result['results']) == 20 and result['candidateCount'] == 40


def test_fallback_order_is_capped_at_the_limit():
    shops = [fake_provider(f'shop{n}', shop_items(f'shop{n}', [f'item {i}' for i in range(10)])) for n in range(3)]
    with patch.object(shops_service, 'enabled_providers', return_value=shops), \
            patch.object(shops_service, 'get_candidate_ranker', side_effect=OSError('missing weights')):
        result = shops_service.rank_shops_response(shops_service.search_shops('item'))
    assert result['rankingStatus'] == 'unavailable' and len(result['results']) == 20 and 'limit' not in result

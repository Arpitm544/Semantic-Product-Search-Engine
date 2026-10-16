"""Shopping provider failures, response safety, and independent source routing."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
import unittest
from unittest.mock import Mock, patch

import requests
from fastapi.testclient import TestClient

from api import main as api, shopping_service as shopping


class TestShoppingSearch(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict('os.environ', {
            'SERPAPI_API_KEY': 'private-test-key', 'SERPAPI_COUNTRY': 'in',
            'SERPAPI_LANGUAGE': 'en', 'SERPAPI_LOCATION': '',
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        shopping._cache.clear()
        shopping._inflight.clear()

    def provider(self, payload=None, status=200):
        response = Mock(status_code=status)
        response.json.return_value = payload
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return patch.object(shopping.requests, 'get', return_value=response)

    def test_normalization_and_cache_preserve_provider_price(self):
        payload = {'shopping_results': [{
            'product_id': '1', 'title': 'Headphones', 'price': '₹2,499.00',
            'extracted_price': 2499, 'source': 'Example store',
            'thumbnail': 'https://example.com/image.jpg',
            'product_link': 'https://www.google.com/search?product=1',
        }]}
        with self.provider(payload) as get:
            result = shopping.search_shopping('headphones')
            cached = shopping.search_shopping('headphones')
        self.assertEqual(result['results'][0]['priceLabel'], '₹2,499.00')
        self.assertEqual(result['results'][0]['merchant'], 'Example store')
        self.assertEqual(result['results'][0]['url'], 'https://www.google.com/search?product=1')
        self.assertIsNone(result['semanticModel'])
        self.assertTrue(cached['cached'])
        get.assert_called_once()
        self.assertEqual(get.call_args.kwargs['params']['gl'], 'in')
        self.assertEqual(get.call_args.kwargs['timeout'], (5, 20))
        self.assertNotIn('private-test-key', str(result))

    def test_empty_query_uses_no_quota(self):
        with patch.object(shopping.requests, 'get') as get:
            self.assertEqual(shopping.search_shopping('')['results'], [])
        get.assert_not_called()

    def test_missing_key(self):
        with patch.dict('os.environ', {'SERPAPI_API_KEY': ''}), patch.object(shopping.requests, 'get') as get:
            with self.assertRaises(shopping.ShoppingError) as caught:
                shopping.search_shopping('phone')
        self.assertEqual(caught.exception.code, 'serpapi_not_configured')
        get.assert_not_called()

    def test_http_failures_are_sanitized_and_not_cached(self):
        for status, expected, code in [(401, 503, 'serpapi_auth'), (403, 503, 'serpapi_auth'),
                                       (429, 429, 'serpapi_quota'), (500, 502, 'serpapi_unavailable')]:
            with self.subTest(status=status), self.provider({'error': 'private-test-key'}, status) as get:
                for _ in range(2):
                    with self.assertRaises(shopping.ShoppingError) as caught:
                        shopping.search_shopping('phone')
                    self.assertEqual(caught.exception.status, expected)
                    self.assertEqual(caught.exception.code, code)
                    self.assertNotIn('private-test-key', str(caught.exception))
                self.assertEqual(get.call_count, 2)

    def test_transport_errors_hide_request_urls_and_keys(self):
        for failure, status in [(requests.Timeout('private-test-key'), 504),
                                (requests.ConnectionError('private-test-key'), 503)]:
            with self.subTest(failure=failure), patch.object(shopping.requests, 'get', side_effect=failure):
                with self.assertRaises(shopping.ShoppingError) as caught:
                    shopping.search_shopping('phone')
                self.assertEqual(caught.exception.status, status)
                self.assertNotIn('private-test-key', str(caught.exception))

    def test_malformed_json_and_provider_errors(self):
        for payload in [[], {'error': 'private-test-key'}, {'search_metadata': {'status': 'Error'}},
                        {'shopping_results': None}]:
            with self.subTest(payload=payload), self.provider(payload):
                with self.assertRaises(shopping.ShoppingError):
                    shopping.search_shopping('phone')
        with self.provider() as get:
            get.return_value.json.side_effect = ValueError('private-test-key')
            with self.assertRaises(shopping.ShoppingError) as caught:
                shopping.search_shopping('phone')
            self.assertNotIn('private-test-key', str(caught.exception))

    def test_empty_results_are_successful(self):
        for payload in [{'shopping_results': []}, {'error': "Google hasn't returned any results for this query."}]:
            shopping._cache.clear()
            with self.provider(payload):
                self.assertEqual(shopping.search_shopping('unknown')['results'], [])

    def test_categorized_results_deduplicate_and_reject_bad_fields(self):
        row = {'product_id': 'one', 'title': 'Phone', 'price': None,
               'extracted_price': float('nan'), 'rating': float('inf'),
               'link': 'javascript:alert(1)', 'thumbnail': 'data:text/html,bad'}
        rows = shopping.normalize_products({
            'shopping_results': [row, None, {'title': ''}],
            'categorized_shopping_results': [{'shopping_results': [row, {'title': 'Laptop'}]}],
        }, 20)
        self.assertEqual(len(rows), 2)
        for field in ('price', 'priceLabel', 'rating', 'url', 'imageUrl'):
            self.assertIsNone(rows[0][field])
        self.assertEqual(len(shopping.normalize_products({'shopping_results': [row, {'title': 'Other'}]}, 1)), 1)

    def test_concurrent_identical_queries_share_one_provider_request(self):
        entered, release = Event(), Event()
        def fetch(_):
            entered.set()
            release.wait(3)
            return {'shopping_results': [{'title': 'Phone'}]}
        with patch.object(shopping, 'fetch_products', side_effect=fetch) as get, ThreadPoolExecutor(2) as pool:
            first = pool.submit(shopping.search_shopping, 'phone')
            self.assertTrue(entered.wait(3))
            second = pool.submit(shopping.search_shopping, 'phone')
            release.set()
            self.assertEqual(first.result()['results'], second.result()['results'])
            get.assert_called_once()

    def test_shopping_route_works_when_mongo_is_not_ready(self):
        with patch.object(api._search_ready, 'is_set', return_value=False), \
                patch.object(api, 'get_search_engine') as engine, self.provider({'shopping_results': []}):
            response = TestClient(api.app).get('/api/search?q=phone&source=serpapi')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['source'], 'serpapi')
        engine.assert_not_called()

    def test_route_rejects_invalid_requests_before_provider_call(self):
        with patch.object(api, 'search_shopping') as search:
            client = TestClient(api.app)
            for params in [{'q': 'phone', 'source': 'other'}, {'q': 'x' * 513, 'source': 'serpapi'}]:
                self.assertEqual(client.get('/api/search', params=params).status_code, 400)
        search.assert_not_called()

    def test_route_surfaces_actionable_errors(self):
        with patch.dict('os.environ', {'SERPAPI_API_KEY': ''}):
            response = TestClient(api.app).get('/api/search?q=phone&source=serpapi')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['code'], 'serpapi_not_configured')
        self.assertIn('SERPAPI_API_KEY', response.json()['error'])


if __name__ == '__main__':
    unittest.main()

"""External products must actually pass through both models, without cache mutation."""

from copy import deepcopy
from threading import Lock
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("authenticated_api")

from api import main as api, shopping_service as shopping
from api.ranking_service import CandidateRanker
from src.search.product_search import ProductSearch


PRODUCTS = [
    {'id': 'serpapi:a', 'title': 'Wired earphones', 'description': 'Wired',
     'priceLabel': '₹499', 'imageUrl': 'https://example.com/a.jpg', 'url': 'https://example.com/a',
     'matchSources': ['google-shopping']},
    {'id': 'serpapi:b', 'title': 'Wireless headphones', 'description': 'Bluetooth over ear',
     'priceLabel': '₹2,499', 'imageUrl': 'https://example.com/b.jpg', 'url': 'https://example.com/b',
     'matchSources': ['google-shopping']},
]


class TestCandidateRanking(unittest.TestCase):
    def setUp(self):
        self.encoder = Mock()
        # Normalized query and product vectors: the second product is a better match.
        self.encoder.encode.return_value = np.array([[1., 0.], [0., 1.], [1., 0.]])
        self.reranker = Mock()
        self.reranker.predict.return_value = np.array([0.1, 0.9])
        self.ranker = CandidateRanker(self.encoder, self.reranker)

    def test_actual_model_scores_reorder_products_and_preserve_display_fields(self):
        products = deepcopy(PRODUCTS)
        results = self.ranker.rank('wireless headphones', products)
        self.assertEqual([p['id'] for p in results], ['serpapi:b', 'serpapi:a'])
        self.encoder.encode.assert_called_once()
        self.reranker.predict.assert_called_once()
        self.assertIn('wireless headphones', self.encoder.encode.call_args.args[0])
        self.assertTrue(self.encoder.encode.call_args.kwargs['normalize_embeddings'])
        self.assertEqual(self.reranker.predict.call_args.args[0][1][0], 'wireless headphones')
        self.assertEqual(results[0]['providerRank'], 2)
        self.assertEqual(results[0]['semanticScore'], 1.)
        self.assertEqual(results[0]['rerankerScore'], 0.9)
        self.assertAlmostEqual(results[0]['score'], 1 / 61)
        for field in ('priceLabel', 'imageUrl', 'url'):
            self.assertEqual(results[0][field], PRODUCTS[1][field])
        self.assertEqual(results[0]['matchSources'], ['google-shopping', 'semantic', 'reranker'])
        self.assertEqual(products, PRODUCTS)

    def test_blend_uses_semantic_and_reranker_ranks(self):
        self.reranker.predict.return_value = [0.9, 0.1]
        results = self.ranker.rank('wireless headphones', PRODUCTS)
        self.assertEqual(results[0]['id'], 'serpapi:a')
        self.assertAlmostEqual(results[0]['score'], 0.25 / 62 + 0.75 / 61)

    def test_ties_keep_provider_order(self):
        self.encoder.encode.return_value = [[1., 0.], [1., 0.], [1., 0.]]
        self.reranker.predict.return_value = [0.5, 0.5]
        self.assertEqual([p['id'] for p in self.ranker.rank('phone', PRODUCTS)], ['serpapi:a', 'serpapi:b'])

    def test_invalid_model_output_is_rejected(self):
        for scores in [[float('nan'), 0.1], [0.1]]:
            self.reranker.predict.return_value = scores
            with self.assertRaises(ValueError):
                self.ranker.rank('phone', PRODUCTS)
        self.encoder.encode.return_value = [[float('inf'), 0.], [0., 1.], [1., 0.]]
        with self.assertRaises(ValueError):
            self.ranker.rank('phone', PRODUCTS)

    def test_shopping_route_uses_our_models_without_mongo(self):
        response = {'query': 'wireless headphones', 'results': deepcopy(PRODUCTS), 'total': 2,
                    'source': 'serpapi', 'semanticModel': None, 'searchMode': 'google-shopping', 'cached': True}
        with patch.object(api, 'search_shopping', return_value=response), \
                patch.object(shopping, 'get_candidate_ranker', return_value=self.ranker), \
                patch.object(api, 'get_search_engine') as mongo, \
                patch.object(api._search_ready, 'is_set', return_value=False):
            result = TestClient(api.app).get('/api/search?q=wireless+headphones&source=serpapi')
        self.assertEqual(result.status_code, 200)
        payload = result.json()
        self.assertEqual(payload['rankingStatus'], 'ranked')
        self.assertEqual(payload['searchMode'], 'google-shopping-semantic-reranked')
        self.assertEqual(payload['semanticModel'], 'fine-tuned')
        self.assertTrue(payload['cached'])
        self.assertEqual(payload['results'][0]['id'], 'serpapi:b')
        mongo.assert_not_called()
        self.assertEqual(response['results'], PRODUCTS)

    def test_missing_models_disclose_unranked_fallback_and_hide_details(self):
        response = {'query': 'phone', 'results': deepcopy(PRODUCTS), 'total': 2,
                    'semanticModel': None, 'searchMode': 'google-shopping'}
        with patch.object(shopping, 'get_candidate_ranker', side_effect=OSError('private-path-or-key')):
            result = shopping.rank_shopping_response(response)
        self.assertEqual(result['rankingStatus'], 'unavailable')
        self.assertEqual(result['results'], PRODUCTS)
        self.assertIsNone(result['semanticModel'])
        self.assertEqual(result['searchMode'], 'google-shopping')
        self.assertIn("Google's original order", result['warning'])
        self.assertNotIn('private-path-or-key', str(result))

    def test_empty_search_skips_models(self):
        with patch.object(shopping, 'get_candidate_ranker') as load:
            result = shopping.rank_shopping_response({'results': []})
        self.assertEqual(result['rankingStatus'], 'empty')
        load.assert_not_called()

    def test_mongo_uses_the_supplied_model_lock(self):
        lock = Lock()
        mongo = ProductSearch(PRODUCTS, None, self.reranker, model_lock=lock)
        self.assertIs(mongo.lock, lock)


if __name__ == '__main__':
    unittest.main()

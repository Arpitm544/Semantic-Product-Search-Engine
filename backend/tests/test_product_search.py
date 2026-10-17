"""Check that product ranking keeps its ordering and result metadata."""

import unittest
from unittest.mock import Mock

from src.search.product_search import ProductSearch


class TestProductSearch(unittest.TestCase):
    def setUp(self):
        self.products = [
            {"id": "a", "title": "Headphones", "representation_text": "headphones audio"},
            {"id": "b", "title": "Wireless headphones", "representation_text": "wireless headphones"},
        ]
        self.reranker = Mock()
        self.engine = ProductSearch(self.products, semantic=None, reranker=self.reranker)

    def test_reranker_and_retrieval_ranks_are_blended(self):
        self.reranker.predict.return_value = [0.1, 0.9]
        ids, scores = self.engine.rank_candidates("headphones", ["a", "b"])
        self.assertEqual(ids, ["b", "a"])
        self.assertAlmostEqual(scores["b"], 0.25 / 62 + 0.75 / 61)
        self.assertAlmostEqual(scores["a"], 0.25 / 61 + 0.75 / 62)

    def test_search_returns_ranked_results_and_match_sources(self):
        self.reranker.predict.return_value = [0.1, 0.9]
        result = self.engine.search("headphones", fuzzy=False)
        self.assertEqual(result["total"], 2)
        self.assertEqual([item["id"] for item in result["results"]], ["b", "a"])
        self.assertEqual(result["queryAlternatives"], ["headphones"])
        for product in result["results"]:
            self.assertIn("keyword", product["matchSources"])
            self.assertIn("reranker", product["matchSources"])

    def test_no_matches_do_not_call_the_reranker(self):
        result = self.engine.search("zzzzzzzz", fuzzy=False)
        self.assertEqual(result["results"], [])
        self.reranker.predict.assert_not_called()


if __name__ == "__main__":
    unittest.main()

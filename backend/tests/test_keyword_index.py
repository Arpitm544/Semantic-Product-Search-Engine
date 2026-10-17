"""Check saved keyword-index compatibility."""

import unittest

from src.keyword_search.bm25 import fit_bm25, search_bm25
class TestBM25Postings(unittest.TestCase):
    def test_saved_legacy_index_matches_new_index_with_repeated_query_terms(self):
        products = [
            {"id": 1, "representation_text": "samsung phone"},
            {"id": 2, "representation_text": "samsung phone phone"},
            {"id": 3, "representation_text": "apple phone"},
        ]
        index = fit_bm25(products)
        expected = search_bm25(index, "phone samsung phone", 10)
        self.assertEqual([p["id"] for p, _ in expected], [2, 1, 3])
        index.pop("postings")
        self.assertEqual(search_bm25(index, "phone samsung phone", 10), expected)


if __name__ == "__main__":
    unittest.main()

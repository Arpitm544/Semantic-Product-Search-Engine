"""
Unit tests for BM25 baseline retrieval and IR metric calculations.
Addresses TR-003, TEST-006, BR-004.
"""
import unittest
from src.baseline.bm25 import BM25Okapi
from src.baseline.evaluate_baseline import (
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    ndcg_at_k,
)


class TestBaseline(unittest.TestCase):

    def test_bm25_search_determinism(self):
        docs = [
            {
                "id": 1,
                "title": "Winter Parka",
                "representation_text": "heavy warm insulated winter parka jacket coat",
            },
            {
                "id": 2,
                "title": "Summer Beach Shorts",
                "representation_text": "lightweight breathable summer swimming shorts",
            },
            {
                "id": 3,
                "title": "Running Shoes",
                "representation_text": "athletic sports running sneakers footwear",
            },
        ]

        bm25 = BM25Okapi().fit(docs)
        res1 = bm25.search("winter jacket parka", top_k=2)
        res2 = bm25.search("winter jacket parka", top_k=2)

        self.assertEqual(len(res1), 1)
        self.assertEqual(res1[0][0]["id"], 1)
        # Deterministic scores across consecutive runs
        self.assertEqual(res1[0][1], res2[0][1])

    def test_ir_metrics_calculation(self):
        retrieved = [10, 20, 30, 40, 50]
        relevant = {20, 30}

        # At k=3: retrieved are [10, 20, 30], hits are 20 and 30 (2 hits)
        p3 = precision_at_k(retrieved, relevant, k=3)
        self.assertAlmostEqual(p3, 2.0 / 3.0, places=4)

        # Recall at k=3: 2 hits out of 2 relevant = 1.0
        r3 = recall_at_k(retrieved, relevant, k=3)
        self.assertAlmostEqual(r3, 1.0, places=4)

        # Reciprocal Rank: first hit is at index 1 (rank 2) -> 1/2 = 0.5
        rr = reciprocal_rank(retrieved, relevant)
        self.assertAlmostEqual(rr, 0.5, places=4)

        # NDCG@3 should be > 0
        ndcg = ndcg_at_k(retrieved, relevant, k=3)
        self.assertGreater(ndcg, 0.0)


if __name__ == "__main__":
    unittest.main()

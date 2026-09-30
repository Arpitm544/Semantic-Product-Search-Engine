"""
Unit tests for Dense Vector Search module (Sentence-BERT + FAISS).
"""
import unittest
import numpy as np

from src.dense.vector_search import DenseVectorSearch


class TestDenseVectorSearch(unittest.TestCase):
    def setUp(self):
        self.sample_products = [
            {
                "id": 1,
                "title": "Wireless Noise Cancelling Headphones",
                "description": "Over-ear Bluetooth headphones with active noise cancellation",
                "category": "electronics",
                "brand": "AudioTech",
                "representation_text": "[Category] electronics | [Brand] AudioTech | [Title] Wireless Noise Cancelling Headphones",
            },
            {
                "id": 2,
                "title": "Leather Running Shoes",
                "description": "Comfortable sneakers for athletics and jogging",
                "category": "footwear",
                "brand": "Speedy",
                "representation_text": "[Category] footwear | [Brand] Speedy | [Title] Leather Running Shoes",
            },
            {
                "id": 3,
                "title": "Smart Watch Fitness Tracker",
                "description": "Heart rate monitor, step counter, waterproof smartwatch",
                "category": "electronics",
                "brand": "FitTech",
                "representation_text": "[Category] electronics | [Brand] FitTech | [Title] Smart Watch Fitness Tracker",
            },
        ]

    def test_fit_and_search(self):
        engine = DenseVectorSearch()
        engine.fit(self.sample_products)

        self.assertIsNotNone(engine.index)
        self.assertEqual(engine.index.ntotal, 3)

        # Search query relevant to headphones
        results = engine.search("audio Bluetooth headset", top_k=2)
        self.assertTrue(len(results) > 0)
        # Top result should be ID 1 (Headphones)
        top_doc, top_score = results[0]
        self.assertEqual(top_doc["id"], 1)

    def test_empty_catalog_raises(self):
        engine = DenseVectorSearch()
        with self.assertRaises(ValueError):
            engine.fit([])


if __name__ == "__main__":
    unittest.main()

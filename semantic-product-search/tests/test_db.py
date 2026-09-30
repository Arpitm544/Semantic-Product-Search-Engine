"""
Unit tests for MongoDB helpers and data loader fallbacks.
"""
import unittest
from unittest.mock import MagicMock, patch
from src.data.db import (
    get_raw_collection,
    get_processed_collection,
    save_raw_products,
    load_raw_products,
    save_processed_products,
    load_processed_products,
    get_products_by_ids,
)
from src.data.load_data import load_raw_products as load_raw_data


class TestMongoDBHelpers(unittest.TestCase):

    def test_save_and_load_raw_products_mock(self):
        mock_collection = MagicMock()
        mock_db = {"products_raw": mock_collection}

        sample_products = [
            {"id": 1, "title": "Product 1", "price": 10.0},
            {"id": 2, "title": "Product 2", "price": 20.0},
        ]

        mock_bulk_result = MagicMock()
        mock_bulk_result.upserted_count = 2
        mock_bulk_result.modified_count = 0
        mock_bulk_result.matched_count = 0
        mock_collection.bulk_write.return_value = mock_bulk_result

        # Test save
        count = save_raw_products(sample_products, db=mock_db)
        self.assertEqual(count, 2)
        mock_collection.bulk_write.assert_called_once()

        # Test load
        mock_collection.find.return_value = sample_products
        loaded = load_raw_products(db=mock_db)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0]["title"], "Product 1")

    def test_get_products_by_ids_mock(self):
        mock_collection = MagicMock()
        mock_db = {"products_processed": mock_collection}

        sample_products = [
            {"id": 1, "title": "Product 1"},
            {"id": 2, "title": "Product 2"},
        ]
        mock_collection.find.return_value = sample_products

        results = get_products_by_ids([2, 1], processed=True, db=mock_db)
        self.assertEqual(len(results), 2)
        # Check ordering is preserved according to request ids
        self.assertEqual(results[0]["id"], 2)
        self.assertEqual(results[1]["id"], 1)

    @patch("src.data.load_data.is_mongo_available", return_value=False)
    def test_load_data_fallback_to_file(self, mock_is_mongo):
        """When MongoDB is unreachable, load_raw_products falls back to a JSON file."""
        import json
        import tempfile
        import os
        from pathlib import Path

        sample = [
            {"id": 1, "title": "Fallback Product A", "price": 9.99},
            {"id": 2, "title": "Fallback Product B", "price": 19.99},
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(sample, f)
            tmp_path = Path(f.name)

        try:
            data = load_raw_data(path=tmp_path, prefer_mongo=False)
            self.assertEqual(len(data), 2)
            self.assertIn("title", data[0])
            self.assertEqual(data[0]["title"], "Fallback Product A")
        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    unittest.main()

"""
Unit tests for data validation, cleaning, and preprocessing.
Addresses TR-002, BR-002, TEST-007.
"""
import unittest
from src.data.validation import validate_catalog
from src.data.preprocess import clean_text, build_representation_text, preprocess_catalog


class TestDataPipeline(unittest.TestCase):

    def test_clean_text(self):
        raw_html = "<p>Product <b>Special</b> Edition &amp; text</p> \n\n"
        cleaned = clean_text(raw_html)
        self.assertNotIn("<p>", cleaned)
        self.assertNotIn("<b>", cleaned)
        self.assertEqual(cleaned, "Product Special Edition &amp; text")

    def test_build_representation_text(self):
        sample = {
            "id": 1,
            "title": "Winter Parka",
            "category": "Jackets",
            "brand": "NorthTrail",
            "description": "Insulated heavy coat for snow.",
            "tags": ["winter", "warm", "waterproof"],
        }
        rep = build_representation_text(sample)
        self.assertIn("[Category] Jackets", rep)
        self.assertIn("[Brand] NorthTrail", rep)
        self.assertIn("[Title] Winter Parka", rep)
        self.assertIn("[Details] Insulated heavy coat for snow.", rep)
        self.assertIn("[Tags] winter, warm, waterproof", rep)

    def test_validate_catalog_valid(self):
        sample_catalog = [
            {
                "id": 1,
                "title": "Item 1",
                "description": "Description 1",
                "category": "cat1",
                "price": 19.99,
            },
            {
                "id": 2,
                "title": "Item 2",
                "description": "Description 2",
                "category": "cat2",
                "price": 49.00,
            },
        ]
        is_valid, report = validate_catalog(sample_catalog)
        self.assertTrue(is_valid)
        self.assertEqual(report["total_records"], 2)
        self.assertEqual(len(report["duplicate_ids"]), 0)

    def test_validate_catalog_invalid(self):
        # Catalog with duplicate IDs and missing title
        invalid_catalog = [
            {"id": 1, "title": "", "description": "Desc", "category": "cat", "price": 10.0},
            {"id": 1, "title": "Dupe", "description": "Desc", "category": "cat", "price": -5.0},
        ]
        is_valid, report = validate_catalog(invalid_catalog)
        self.assertFalse(is_valid)
        self.assertIn(1, report["duplicate_ids"])
        self.assertEqual(report["missing_fields"]["title"], 1)
        self.assertEqual(report["invalid_prices"], 1)


if __name__ == "__main__":
    unittest.main()

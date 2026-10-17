"""Verify MongoDB catalog reads and import readiness without a live database."""

import unittest
from unittest.mock import MagicMock, patch

from src.data import catalog as catalog


class TestCatalog(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.manifest = {"status": "ready", "product_count": 2}
        self.db["catalog_manifests"].find_one.return_value = self.manifest
        self.products = [{"id": "esci:us:1"}, {"id": "esci:us:2"}]
        self.db[catalog.COLLECTION].find.return_value.sort.return_value = self.products
        self.database_patch = patch.object(catalog, "database", return_value=self.db)
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)

    def test_only_the_configured_catalog_is_loaded(self):
        self.assertEqual(catalog.load_products(), self.products)
        self.db[catalog.COLLECTION].find.assert_called_once_with({}, {"_id": 0})
        self.db[catalog.COLLECTION].find.return_value.sort.assert_called_once_with("id", 1)

    def test_missing_manifest_prevents_serving(self):
        self.db["catalog_manifests"].find_one.return_value = None
        with self.assertRaisesRegex(ValueError, "not ready"):
            catalog.load_products()
        self.db[catalog.COLLECTION].find.assert_not_called()

    def test_incomplete_import_prevents_serving(self):
        self.manifest["status"] = "importing"
        with self.assertRaisesRegex(catalog.CatalogUpdatingError, "in progress"):
            catalog.load_products()

    def test_catalog_count_must_match_the_import_manifest(self):
        self.manifest["product_count"] = 3
        with self.assertRaisesRegex(ValueError, "count differs"):
            catalog.load_products()


if __name__ == "__main__":
    unittest.main()

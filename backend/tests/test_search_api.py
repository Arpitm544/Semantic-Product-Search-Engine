"""Check the API's typo contract and catalog cache without downloading models."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from threading import Event
import numpy as np

from api import main as api
from src.search.hybrid import HybridSearch


PRODUCTS = [
    {"id": 1, "title": "Samsung Galaxy", "representation_text": "samsung galaxy"},
    {"id": 2, "title": "Mascara", "representation_text": "mascara makeup"},
]


def request(route, engine):
    handler = object.__new__(api.ApiHandler)
    handler.path = route
    handler.write_json = Mock()
    ready = Event()
    ready.set()
    with patch.object(api, "_search_ready", ready), \
            patch.object(api, "get_search_engine", return_value=engine):
        handler.do_GET()
    return handler.write_json.call_args.args


class TestSearchAPI(unittest.TestCase):
    def test_search_returns_suggestion_and_matching_product(self):
        status, payload = request("/api/search?q=samsng", HybridSearch(PRODUCTS))
        self.assertEqual(status, 200)
        self.assertEqual(payload["query"], "samsng")
        self.assertEqual(payload["correctedQuery"], "samsung")
        self.assertEqual(payload["results"][0]["id"], 1)

    def test_original_query_can_disable_fuzzy_matching(self):
        status, payload = request("/api/search?q=samsng&fuzzy=0", HybridSearch(PRODUCTS))
        self.assertEqual(status, 200)
        self.assertIsNone(payload["correctedQuery"])
        self.assertEqual(payload["results"], [])

    def test_query_length_is_bounded(self):
        status, payload = request("/api/search?q=" + "a" * 513, HybridSearch(PRODUCTS))
        self.assertEqual(status, 400)
        self.assertIn("512", payload["error"])

    def test_catalog_indexes_are_reused_and_refreshed_after_a_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            weights = root / "models/esci-minilm-20k/model.safetensors"
            weights.parent.mkdir(parents=True)
            weights.touch()
            manifest = {"sha256": "first", "updated_at": "1"}
            semantic = Mock()
            semantic.index.reconstruct_n.return_value = np.array([[1., 0.], [0., 1.]], dtype=np.float32)
            with patch.object(api, "PROJECT_ROOT", root), \
                    patch.object(api, "version", side_effect=lambda: dict(manifest)), \
                    patch.object(api, "load_products", return_value=PRODUCTS) as catalog, \
                    patch.object(api, "_search_engine", None), \
                    patch.object(api, "_search_signature", None), \
                    patch.dict("os.environ", {"SEMANTIC_MODEL_PATH": "models/esci-minilm-20k"}), \
                    patch("src.semantic.vector_search.SemanticVectorSearch", return_value=semantic), \
                    patch("sentence_transformers.CrossEncoder"), \
                    patch.object(api, "AmazonSearch", side_effect=lambda *args: Mock()) as factory:
                first = api.get_search_engine()
                self.assertIs(first, api.get_search_engine())
                self.assertEqual(catalog.call_count, 1)
                manifest.update(sha256="second", updated_at="2")
                refreshed = api.get_search_engine()
                self.assertIsNot(first, refreshed)
                self.assertEqual(catalog.call_count, 2)
                self.assertEqual(factory.call_count, 2)
                self.assertEqual(semantic.fit.call_count, 2)

    def test_missing_catalog_returns_service_error(self):
        handler = object.__new__(api.ApiHandler)
        handler.path = "/api/search?q=laptop"
        handler.write_json = Mock()
        ready = Event()
        ready.set()
        with patch.object(api, "_search_ready", ready), \
                patch.object(api, "get_search_engine", side_effect=FileNotFoundError("Missing catalog")):
            handler.do_GET()
        self.assertEqual(handler.write_json.call_args.args, (503, {"error": "Missing catalog"}))


if __name__ == "__main__":
    unittest.main()

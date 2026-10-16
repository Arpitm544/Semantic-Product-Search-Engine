"""Check catalog-only API behavior without downloading models or opening MongoDB."""

import unittest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from api import main as api
from api import search_service, dashboard
from src.search.hybrid import HybridSearch


PRODUCTS = [
    {"id": "esci:us:1", "title": "Samsung Galaxy", "representation_text": "samsung galaxy"},
    {"id": "esci:us:2", "title": "Mascara", "representation_text": "mascara makeup"},
]


def request(route, engine):
    # Without a context manager, TestClient skips model-loading startup.
    with patch.object(api._search_ready, "is_set", return_value=True), \
            patch.object(api, "get_search_engine", return_value=engine):
        response = TestClient(api.app).get(route)
    return response.status_code, response.json()


class TestSearchAPI(unittest.TestCase):
    def test_health_reports_initializing_and_ready(self):
        for ready, status in [(False, 503), (True, 200)]:
            with self.subTest(ready=ready), \
                    patch.object(api._search_ready, "is_set", return_value=ready), \
                    patch.object(api, "_search_error", None):
                response = TestClient(api.app).get("/api/health")
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.json()["ok"], ready)
            self.assertEqual(response.headers["cache-control"], "no-store")

    def test_cors_allows_frontend_and_rejects_unknown_origin(self):
        client = TestClient(api.app)
        for origin, status in [(api.FRONTEND_ORIGINS[0], 200), ("https://unknown.example", 400)]:
            response = client.options("/api/search", headers={
                "Origin": origin, "Access-Control-Request-Method": "GET",
            })
            self.assertEqual(response.status_code, status)

    def test_startup_initializes_search_in_background(self):
        with patch.object(api, "Thread") as thread:
            with TestClient(api.app):
                thread.assert_called_once_with(target=api.initialize_search, daemon=True)
                thread.return_value.start.assert_called_once_with()

    def test_initialization_failure_is_reported_by_health(self):
        with patch.object(api, "_search_error", None), \
                patch.object(api._search_ready, "is_set", return_value=False), \
                patch.object(api, "get_search_engine", side_effect=ValueError("Missing model")):
            api.initialize_search()
            response = TestClient(api.app).get("/api/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "error")
        self.assertIn("Missing model", response.json()["message"])

    def test_search_returns_suggestion_and_matching_product(self):
        status, payload = request("/api/search?q=samsng", HybridSearch(PRODUCTS))
        self.assertEqual(status, 200)
        self.assertEqual(payload["query"], "samsng")
        self.assertEqual(payload["correctedQuery"], "samsung")
        self.assertEqual(payload["results"][0]["id"], "esci:us:1")

    def test_original_query_can_disable_fuzzy_matching(self):
        status, payload = request("/api/search?q=samsng&fuzzy=0", HybridSearch(PRODUCTS))
        self.assertEqual(status, 200)
        self.assertIsNone(payload["correctedQuery"])
        self.assertEqual(payload["results"], [])

    def test_query_length_is_bounded(self):
        status, payload = request("/api/search?q=" + "a" * 513, HybridSearch(PRODUCTS))
        self.assertEqual(status, 400)
        self.assertIn("512", payload["error"])

    def test_unchanged_mongo_version_reuses_the_search_index(self):
        manifest = {"sha256": "catalog-sha", "updated_at": "import-time"}
        signature = ("catalog-sha", "import-time", "model", "reranker")
        engine = Mock()
        with patch.object(search_service, "version", return_value=manifest), \
                patch.object(search_service, "_search_engine", engine), \
                patch.object(search_service, "_search_signature", signature), \
                patch.object(search_service, "load_products") as load, \
                patch.dict("os.environ", {"SEMANTIC_MODEL_PATH": "model", "RERANKER_MODEL_PATH": "reranker"}):
            self.assertIs(search_service.get_search_engine(), engine)
            load.assert_not_called()

    def test_new_mongo_version_requires_reloading_the_catalog(self):
        with patch.object(search_service, "version", return_value={"sha256": "new", "updated_at": "new-time"}), \
                patch.object(search_service, "_search_engine", Mock()), \
                patch.object(search_service, "_search_signature", ("old", "old-time", "model", "reranker")), \
                patch.object(search_service, "load_products", side_effect=ValueError("Catalog unavailable")) as load:
            with self.assertRaisesRegex(ValueError, "Catalog unavailable"):
                search_service.get_search_engine()
            load.assert_called_once_with()

    def test_missing_catalog_returns_service_error(self):
        engine = Mock()
        engine.search.side_effect = ValueError("Missing catalog")
        self.assertEqual(request("/api/search?q=laptop", engine), (503, {"error": "Missing catalog"}))

    def test_initializing_search_is_unavailable(self):
        with patch.object(api._search_ready, "is_set", return_value=False), \
                patch.object(api, "_search_error", None), \
                patch.object(api, "get_search_engine") as engine:
            response = TestClient(api.app).get("/api/search?q=laptop")
        self.assertEqual(response.status_code, 503)
        engine.assert_not_called()

    def test_dashboard_reads_the_mongo_catalog(self):
        with patch.object(dashboard, "load_products", return_value=PRODUCTS) as load:
            response = TestClient(api.app).get("/api/dashboard")
            self.assertEqual(response.status_code, 200)
            summary = response.json()
        load.assert_called_once_with()
        self.assertEqual(summary["productCount"], 2)
        self.assertEqual(summary["sources"]["catalog"], f"MongoDB/{dashboard.COLLECTION}")
        self.assertNotIn("evalQueries", summary)
        self.assertNotIn("benchmark", summary)


if __name__ == "__main__":
    unittest.main()

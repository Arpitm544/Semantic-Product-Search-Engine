from unittest.mock import patch
from fastapi.testclient import TestClient
from api import main as api


def test_public_ping_does_not_touch_search_or_database():
    with patch.object(api, "get_search_engine", side_effect=AssertionError("must not load models")), \
            patch.object(api._search_ready, "is_set", return_value=False):
        client = TestClient(api.app)
        for path in ("/healthz", "/api/health/live"):
            response = client.get(path)
            assert response.status_code == 200
            assert response.json()["ok"] is True
            assert response.headers["cache-control"] == "no-store"

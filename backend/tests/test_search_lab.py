from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from api import main as api
from src.search.product_search import ProductSearch


def test_lab_fuses_the_same_candidates_without_reranking(monkeypatch, authenticated_api):
    products = [
        {"id": "a", "title": "Wireless"},
        {"id": "b", "title": "Wireless headphones"},
        {"id": "c", "title": "Bluetooth earbuds"},
    ]
    semantic = Mock()
    semantic.search.return_value = [(products[2], 0.95), (products[1], 0.85)]
    reranker = Mock()
    engine = ProductSearch(products, semantic, reranker)
    monkeypatch.setattr(api._search_ready, "is_set", lambda: True)
    monkeypatch.setattr(api, "get_search_engine", lambda: engine)

    response = TestClient(api.app).get("/api/search-lab", params={"q": "  wireless  "})

    assert response.status_code == 200
    assert response.json() == {
        "query": "wireless",
        "limit": 10,
        "rankings": {
            "keyword": [
                {"id": "a", "title": "Wireless"},
                {"id": "b", "title": "Wireless headphones"},
            ],
            "semantic": [
                {"id": "c", "title": "Bluetooth earbuds"},
                {"id": "b", "title": "Wireless headphones"},
            ],
            "hybrid": [
                {"id": "b", "title": "Wireless headphones"},
                {"id": "a", "title": "Wireless"},
                {"id": "c", "title": "Bluetooth earbuds"},
            ],
        },
    }
    semantic.search.assert_called_once_with("wireless", 3)
    reranker.predict.assert_not_called()


@pytest.mark.parametrize("query", ["   ", "a" * 513])
def test_lab_rejects_invalid_queries_before_search(monkeypatch, authenticated_api, query):
    get_engine = Mock()
    monkeypatch.setattr(api, "get_search_engine", get_engine)

    response = TestClient(api.app).get("/api/search-lab", params={"q": query})

    assert response.status_code == 400
    get_engine.assert_not_called()


def test_lab_requires_catalog_authentication(monkeypatch):
    get_engine = Mock()
    monkeypatch.setattr(api, "get_search_engine", get_engine)

    response = TestClient(api.app).get("/api/search-lab", params={"q": "wireless"})

    assert response.status_code == 401
    get_engine.assert_not_called()

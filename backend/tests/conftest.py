"""Reusable authenticated context for API behavior tests."""
import pytest
from unittest.mock import patch


@pytest.fixture
def authenticated_api():
    from api.main import app
    from api.auth import require_session
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[require_session] = lambda: {"sub": "user_test", "sid": "sess_test"}
    # Keep API behavior tests from persisting developer search history.
    with patch("api.main.remember_search", side_effect=lambda user, search, payload: payload):
        yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


@pytest.fixture(autouse=True)
def no_background_price_checks(monkeypatch):
    # Unit/API tests never start a real price-monitoring thread or spend API quota.
    monkeypatch.setenv('PRICE_ALERTS_ENABLED', '0')

"""Reusable authenticated context for API behavior tests."""
import pytest


@pytest.fixture
def authenticated_api():
    from api.main import app
    from api.auth import require_session
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[require_session] = lambda: {"sub": "user_test", "sid": "sess_test"}
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)

"""Security regressions: real JWT signatures, claims, API guards, and CORS."""
import base64
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from api import auth, main


@pytest.fixture
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def claims(**overrides):
    now = int(time.time())
    return {"iss": "https://test.clerk.accounts.dev", "sub": "user_test", "sid": "sess_test",
            "iat": now, "nbf": now - 5, "exp": now + 60, "azp": "http://localhost:3001", **overrides}


def verify(key, payload, algorithm="RS256"):
    token = jwt.encode(payload, key if algorithm == "RS256" else "invalid-secret-that-is-long-enough-for-hs256", algorithm=algorithm)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    client = Mock()
    client.get_signing_key_from_jwt.return_value = SimpleNamespace(key=key.public_key())
    with patch.dict("os.environ", {"CLERK_ISSUER_URL": "https://test.clerk.accounts.dev",
                                   "FRONTEND_ORIGINS": "http://localhost:3001"}), \
            patch.object(auth, "jwks_client", return_value=client):
        return auth.require_session(credentials)


def test_valid_session(signing_key):
    assert verify(signing_key, claims())["sub"] == "user_test"


@pytest.mark.parametrize("changes", [
    {"exp": int(time.time()) - 60}, {"nbf": int(time.time()) + 300},
    {"iss": "https://attacker.example"}, {"azp": "https://attacker.example"},
    {"sub": ""}, {"sid": ""}, {"sts": "pending"}, {"azp": None},
])
def test_reject_invalid_claims(signing_key, changes):
    with pytest.raises(HTTPException) as error:
        verify(signing_key, claims(**changes))
    assert error.value.status_code == 401


@pytest.mark.parametrize("missing", ["exp", "nbf", "iat", "iss", "sub", "sid"])
def test_require_security_claims(signing_key, missing):
    payload = claims()
    del payload[missing]
    with pytest.raises(HTTPException) as error:
        verify(signing_key, payload)
    assert error.value.status_code == 401


def test_reject_wrong_algorithm(signing_key):
    with pytest.raises(HTTPException) as error:
        verify(signing_key, claims(), "HS256")
    assert error.value.status_code == 401


def test_reject_forged_signature(signing_key):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(claims(), other, algorithm="RS256")
    client = Mock()
    client.get_signing_key_from_jwt.return_value = SimpleNamespace(key=signing_key.public_key())
    with patch.object(auth, "issuer_url", return_value="https://test.clerk.accounts.dev"), \
            patch.object(auth, "jwks_client", return_value=client), pytest.raises(HTTPException) as error:
        auth.require_session(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    assert error.value.status_code == 401


@pytest.mark.parametrize("path", ["/api/search?q=headphones", "/api/dashboard"])
def test_api_requires_session(path):
    response = TestClient(main.app).get(path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_health_remains_public():
    assert TestClient(main.app).get("/api/health").status_code in (200, 503)


def test_cors_accepts_authorization():
    response = TestClient(main.app).options("/api/search", headers={
        "Origin": main.FRONTEND_ORIGINS[0], "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization",
    })
    assert response.status_code == 200


def test_missing_configuration_fails_closed():
    with patch.dict("os.environ", {"CLERK_ISSUER_URL": "", "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": ""}), \
            pytest.raises(HTTPException) as error:
        auth.require_session(HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid"))
    assert error.value.status_code == 503


@pytest.mark.parametrize("issuer", [
    "http://test.clerk.accounts.dev", "https://", "https://example.com/path",
    "https://example.com?query=1", "https://example.com#fragment",
    "https://user@example.com", "https://user:password@example.com",
])
def test_reject_invalid_issuer_urls(issuer):
    with patch.dict("os.environ", {"CLERK_ISSUER_URL": issuer}), \
            pytest.raises(HTTPException) as error:
        auth.issuer_url()
    assert error.value.status_code == 503


@pytest.mark.parametrize("prefix", ["pk_test_", "pk_live_"])
def test_issuer_from_publishable_key(prefix):
    encoded = base64.b64encode(b"test.clerk.accounts.dev$").decode().rstrip("=")
    with patch.dict("os.environ", {"CLERK_ISSUER_URL": "",
                                   "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": prefix + encoded}):
        assert auth.issuer_url() == "https://test.clerk.accounts.dev"


def test_explicit_issuer_takes_precedence():
    with patch.dict("os.environ", {"CLERK_ISSUER_URL": "https://example.com/",
                                   "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": "invalid"}):
        assert auth.issuer_url() == "https://example.com"


def test_frontend_origins_ignore_whitespace_and_empty_entries():
    with patch.dict("os.environ", {"FRONTEND_ORIGINS": " http://localhost:3001, ,http://localhost:3001,"}):
        assert auth.frontend_origins() == {"http://localhost:3001"}


def test_jwks_connection_failure_is_service_unavailable():
    client = Mock()
    client.get_signing_key_from_jwt.side_effect = jwt.PyJWKClientConnectionError("offline")
    with patch.object(auth, "issuer_url", return_value="https://test.clerk.accounts.dev"), \
            patch.object(auth, "jwks_client", return_value=client), pytest.raises(HTTPException) as error:
        auth.require_session(HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"))
    assert error.value.status_code == 503

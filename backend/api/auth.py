"""Verify Clerk bearer sessions before serving protected search data."""
import base64
from functools import lru_cache
import os
import ssl

import certifi
from urllib.parse import urlparse

import jwt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import Depends

bearer = HTTPBearer(auto_error=False)


def issuer_url():
    issuer = os.environ.get("CLERK_ISSUER_URL", "").rstrip("/")
    if not issuer:
        # The development launcher forwards the public frontend configuration.
        key = os.environ.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "")
        if key.startswith(("pk_test_", "pk_live_")):
            try:
                value = key.split("_", 2)[2]
                host = base64.b64decode(value + "=" * (-len(value) % 4)).decode().rstrip("$")
                issuer = "https://" + host
            except (ValueError, UnicodeError):
                pass
    parsed = urlparse(issuer)
    if parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise HTTPException(503, "Configure CLERK_ISSUER_URL before using the API.")
    return issuer


@lru_cache(maxsize=4)
def jwks_client(issuer):
    return jwt.PyJWKClient(issuer + "/.well-known/jwks.json", timeout=5, lifespan=300,
                           ssl_context=ssl.create_default_context(cafile=certifi.where()))


def require_session(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    if not credentials:
        raise HTTPException(401, "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
    issuer = issuer_url()
    origins = {v.strip() for v in os.environ.get(
        "FRONTEND_ORIGINS", "http://localhost:3001,http://127.0.0.1:3001"
    ).split(",") if v.strip()}
    try:
        key = jwks_client(issuer).get_signing_key_from_jwt(credentials.credentials)
        claims = jwt.decode(credentials.credentials, key.key, algorithms=["RS256"], issuer=issuer,
                            options={"require": ["exp", "nbf", "iat", "iss", "sub", "sid"], "verify_aud": False})
        if not claims.get("sub") or not claims.get("sid") or claims.get("sts") == "pending":
            raise jwt.InvalidTokenError("Inactive session")
        if claims.get("azp") not in origins:
            raise jwt.InvalidTokenError("Invalid authorized party")
        return claims
    except jwt.PyJWKClientConnectionError:
        raise HTTPException(503, "Authentication service temporarily unavailable.") from None
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(401, "Invalid or expired session.", headers={"WWW-Authenticate": "Bearer"}) from None

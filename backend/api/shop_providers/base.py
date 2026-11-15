"""Shared helpers for free online-shop product providers.

Each provider turns its own API response into the product shape the search page
already uses for Google Shopping results, so ranking, saving, and display work
unchanged.
"""
from datetime import datetime, timezone
import os
from threading import Lock

import requests

from api.shopping_service import number, public_url, text

TIMEOUT = (5, 10)


class ProviderError(Exception):
    """A sanitized provider failure. Never include tokens or response bodies."""

    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


class DailyBudget:
    """Per-process daily call cap that keeps one provider inside its free quota.

    The backend runs one worker, so an in-memory counter is enough. It resets at
    the start of each UTC day.
    """

    def __init__(self, env_name, default):
        self.env_name = env_name
        self.default = default
        self._lock = Lock()
        self._day = None
        self._used = 0

    def limit(self):
        try:
            return max(0, int(os.environ.get(self.env_name, str(self.default))))
        except ValueError:
            return self.default

    def take(self):
        today = datetime.now(timezone.utc).date()
        with self._lock:
            if self._day != today:
                self._day, self._used = today, 0
            if self._used >= self.limit():
                return False
            self._used += 1
            return True


def get_json(url, provider, **kwargs):
    """GET a provider endpoint with bounded timeouts and sanitized errors."""
    try:
        response = requests.get(url, timeout=TIMEOUT, allow_redirects=False, **kwargs)
    except requests.Timeout:
        raise ProviderError(f'{provider} took too long to respond.', 'timeout') from None
    except requests.RequestException:
        raise ProviderError(f'Cannot reach {provider} right now.', 'unavailable') from None
    with response:
        status = response.status_code
        if status in (401, 403):
            raise ProviderError(f'{provider} rejected the configured credentials.', 'auth')
        if status == 429:
            raise ProviderError(f'{provider} request limit reached.', 'quota')
        if status != 200:
            raise ProviderError(f'{provider} is unavailable right now.', 'unavailable')
        try:
            payload = response.json()
        except ValueError:
            raise ProviderError(f'{provider} returned an invalid response.', 'invalid_response') from None
    if not isinstance(payload, dict):
        raise ProviderError(f'{provider} returned an invalid response.', 'invalid_response')
    return payload


def product(*, provider, merchant, identity, title, description='', price=None, currency=None,
            image=None, url=None, brand=None, category=None, in_stock=None, attributes=()):
    """Build one result in the shared search-result shape, or None if unusable."""
    title = text(title)
    identity = text(str(identity)) if identity is not None else ''
    if not title or not identity:
        return None
    currency = text(currency).upper() or None
    return {
        'id': f'{provider}:{identity}',
        'title': title[:500],
        'description': text(description)[:2000],
        'merchant': merchant,
        'price': number(price),
        'currency': currency if currency and len(currency) == 3 else None,
        'priceLabel': None,
        'imageUrl': public_url(image),
        'url': public_url(url),
        'brand': text(brand) or None,
        'category': text(category) or None,
        'inStock': in_stock if isinstance(in_stock, bool) else None,
        'rating': None,
        'reviews': None,
        'attributes': [text(value)[:500] for value in attributes if text(value)][:40],
        'provider': provider,
        'matchSources': [provider],
    }

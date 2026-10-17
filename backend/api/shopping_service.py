"""Fetch Google Shopping results through SerpApi without exposing credentials."""

from collections import OrderedDict
from concurrent.futures import Future, TimeoutError as FutureTimeout
import hashlib
import math
import logging
import os
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit

import requests

from api.ranking_service import get_candidate_ranker

logger = logging.getLogger(__name__)


ENDPOINT = "https://serpapi.com/search.json"
CACHE_SECONDS = 300
CACHE_SIZE = 128
_cache = OrderedDict()
_cache_lock = Lock()
_inflight = {}


class ShoppingError(Exception):
    """A public, sanitized error suitable for the search API response."""

    def __init__(self, message, code, status=502):
        super().__init__(message)
        self.code = code
        self.status = status


def text(value):
    return value.strip() if isinstance(value, str) else ""


def public_url(value):
    """Only pass ordinary web links through to product cards."""
    value = text(value)
    try:
        parsed = urlsplit(value)
        if parsed.scheme in ("https", "http") and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return None


def number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def normalize_products(payload, limit):
    """Handle both flat and categorized organic Google Shopping layouts."""
    rows = payload.get("shopping_results", [])
    if not isinstance(rows, list):
        raise ShoppingError("Shopping search returned an invalid response. Please try again.", "serpapi_invalid_response")
    rows = list(rows)
    groups = payload.get("categorized_shopping_results", [])
    if isinstance(groups, list):
        for group in groups:
            if isinstance(group, dict) and isinstance(group.get("shopping_results"), list):
                rows.extend(group["shopping_results"])

    results, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or not text(row.get("title")):
            continue
        url = public_url(row.get("link")) or public_url(row.get("product_link"))
        identity = str(row.get("product_id") or url or f"{row['title']}:{row.get('source', '')}")
        if identity in seen:
            continue
        seen.add(identity)
        rating = number(row.get("rating"))
        results.append({
            "id": f"serpapi:{identity}",
            "title": text(row.get("title")),
            "description": text(row.get("snippet")),
            "merchant": text(row.get("source")),
            "price": number(row.get("extracted_price")),
            # Preserve the provider's currency instead of guessing from the country.
            "priceLabel": text(row.get("price")) or None,
            "imageUrl": public_url(row.get("thumbnail")),
            "url": url,
            "rating": rating if rating is not None and rating <= 5 else None,
            "reviews": number(row.get("reviews")),
            "matchSources": ["google-shopping"],
        })
        if len(results) >= limit:
            break
    return results


def fetch_products(params):
    """Use bounded timeouts; never include provider bodies or request URLs in errors."""
    try:
        response = requests.get(ENDPOINT, params=params, timeout=(5, 20), allow_redirects=False)
    except requests.Timeout:
        raise ShoppingError("Google Shopping took too long to respond. Please try again.", "serpapi_timeout", 504) from None
    except requests.RequestException:
        raise ShoppingError("Cannot reach shopping search right now. Please try again shortly.", "serpapi_unavailable", 503) from None

    with response:
        if response.status_code in (401, 403):
            raise ShoppingError("Shopping search credentials were rejected. Check SERPAPI_API_KEY on the backend.", "serpapi_auth", 503)
        if response.status_code == 429:
            raise ShoppingError("Shopping search has reached its request limit or monthly quota. Try later or choose MongoDB.", "serpapi_quota", 429)
        if response.status_code != 200:
            raise ShoppingError("Shopping search is unavailable right now. Please try again shortly.", "serpapi_unavailable", 502)
        try:
            payload = response.json()
        except ValueError:
            raise ShoppingError("Shopping search returned an invalid response. Please try again.", "serpapi_invalid_response") from None

    if not isinstance(payload, dict):
        raise ShoppingError("Shopping search returned an invalid response. Please try again.", "serpapi_invalid_response")
    provider_error = text(payload.get("error"))
    # SerpApi can report a legitimate empty search as an error in a 200 response.
    if provider_error.startswith("Google hasn't returned any results for this query"):
        return {"shopping_results": []}
    metadata = payload.get("search_metadata")
    if payload.get("error") or (isinstance(metadata, dict) and metadata.get("status") in ("Error", "Processing", "Queued")):
        raise ShoppingError("Shopping search could not complete this request. Please try again shortly.", "serpapi_provider_error")
    return payload


def search_shopping(query, limit=20):
    response = {
        "query": query, "source": "serpapi", "searchMode": "google-shopping",
        "semanticModel": None, "correctedQuery": None, "corrections": [],
        "total": 0, "results": [], "cached": False,
    }
    if not query:
        return response
    api_key = os.environ.get("SERPAPI_API_KEY", "").strip()
    if not api_key:
        raise ShoppingError("Google Shopping is not configured. Set SERPAPI_API_KEY in backend/.env and restart the backend, or choose MongoDB.", "serpapi_not_configured", 503)

    params = {
        "engine": "google_shopping", "api_key": api_key, "q": query,
        "gl": os.environ.get("SERPAPI_COUNTRY", "in").strip() or "in",
        "hl": os.environ.get("SERPAPI_LANGUAGE", "en").strip() or "en",
    }
    location = os.environ.get("SERPAPI_LOCATION", "").strip()
    if location:
        params["location"] = location
    cache_key = (hashlib.sha256(api_key.encode()).hexdigest(), query, params["gl"], params["hl"], location, limit)

    # Share concurrent requests for the same query without blocking other queries.
    # Failures are not cached and requests are not automatically retried.
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and monotonic() - cached[0] < CACHE_SECONDS:
            _cache.move_to_end(cache_key)
            return {**response, "results": cached[1], "total": len(cached[1]), "cached": True}
        waiting = _inflight.get(cache_key)
        if waiting is None:
            _inflight[cache_key] = Future()
    if waiting is not None:
        try:
            products = waiting.result(timeout=30)
        except FutureTimeout:
            raise ShoppingError("Google Shopping took too long to respond. Please try again.", "serpapi_timeout", 504) from None
        return {**response, "results": products, "total": len(products), "cached": True}
    try:
        products = normalize_products(fetch_products(params), limit)
    except Exception as error:
        with _cache_lock:
            _inflight.pop(cache_key).set_exception(error)
        raise
    with _cache_lock:
        _cache[cache_key] = (monotonic(), products)
        _cache.move_to_end(cache_key)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
        _inflight.pop(cache_key).set_result(products)
    return {**response, "results": products, "total": len(products)}


def rank_shopping_response(response):
    """Apply our models to cached or freshly fetched provider candidates."""
    if not response['results']:
        return {**response, 'rankingStatus': 'empty'}
    try:
        results = get_candidate_ranker().rank(response['query'], response['results'])
    except Exception as error:
        # Keep shopping usable if local weights cannot load. Disclose the fallback
        # and never expose exception details or claim semantic ranking occurred.
        logger.warning('Shopping model ranking failed (%s).', type(error).__name__, exc_info=True)
        return {
            **response, 'rankingStatus': 'unavailable',
            'warning': "Our search models are unavailable. Showing Google's original order. Please try again shortly.",
            'warningCode': 'shopping_ranking_unavailable',
        }
    return {
        **response, 'results': results, 'searchMode': 'google-shopping-semantic-reranked',
        'semanticModel': 'fine-tuned', 'rankingStatus': 'ranked',
    }

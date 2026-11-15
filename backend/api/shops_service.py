"""Search several free online-shop APIs at once and rank the merged results.

Providers are queried in parallel with a shared deadline, so one slow shop
cannot hold up the others. A shop that fails is reported in `providers` while
the rest still return results. Results are cached per shop for five minutes.
"""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, wait
import logging
from threading import Lock
from time import monotonic

from api.ranking_service import get_candidate_ranker
from api.shop_providers import enabled_providers
from api.shop_providers.base import ProviderError
from api.shopping_service import ShoppingError

logger = logging.getLogger(__name__)

PER_PROVIDER = 10
DEADLINE_SECONDS = 15
CACHE_SECONDS = 300
CACHE_SIZE = 256
_cache = OrderedDict()
_cache_lock = Lock()
_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix='shop-search')


def cached(name, query):
    with _cache_lock:
        entry = _cache.get((name, query))
        if entry and monotonic() - entry[0] < CACHE_SECONDS:
            _cache.move_to_end((name, query))
            return entry[1]
    return None


def remember(name, query, results):
    with _cache_lock:
        _cache[(name, query)] = (monotonic(), results)
        _cache.move_to_end((name, query))
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)


def fetch(provider, query):
    hit = cached(provider.NAME, query)
    if hit is not None:
        return hit, True
    results = provider.search(query, PER_PROVIDER)
    remember(provider.NAME, query, results)
    return results, False


def interleave(lists, limit):
    """Take results round-robin so no single shop crowds out the others."""
    merged, seen = [], set()
    for position in range(max((len(items) for items in lists), default=0)):
        for items in lists:
            if position < len(items) and items[position]['id'] not in seen:
                seen.add(items[position]['id'])
                merged.append(items[position])
    return merged[:limit]


def search_shops(query, limit=20):
    response = {
        'query': query, 'source': 'shops', 'searchMode': 'online-shops',
        'semanticModel': None, 'correctedQuery': None, 'corrections': [],
        'total': 0, 'results': [], 'providers': [],
    }
    if not query:
        return response
    providers = enabled_providers()
    if not providers:
        raise ShoppingError('No online shops are configured. Add eBay or Flipkart API keys in backend/.env '
                            'and restart the backend, or choose another source.', 'shops_not_configured', 503)

    futures = {_pool.submit(fetch, provider, query): provider for provider in providers}
    done, _ = wait(futures, timeout=DEADLINE_SECONDS)
    lists = []
    for future, provider in futures.items():
        status = {'name': provider.NAME, 'label': provider.LABEL}
        if future not in done:
            future.cancel()
            status.update(status='timeout', message=f'{provider.LABEL} took too long to respond.', count=0)
        else:
            try:
                results, from_cache = future.result()
                lists.append(results)
                status.update(status='ok', count=len(results), cached=from_cache)
            except ProviderError as error:
                status.update(status=error.code, message=str(error), count=0)
            except Exception:
                logger.exception('%s search failed unexpectedly', provider.LABEL)
                status.update(status='error', message=f'{provider.LABEL} search failed.', count=0)
        response['providers'].append(status)

    if not lists:
        raise ShoppingError('None of the configured online shops responded. Please try again shortly.',
                            'shops_unavailable', 503)
    results = interleave(lists, limit)
    response.update(results=results, total=len(results))
    failed = [item['label'] for item in response['providers'] if item['status'] != 'ok']
    if failed:
        response['warning'] = f"Results from {', '.join(failed)} are unavailable right now."
    return response


def rank_shops_response(response):
    """Rank merged shop results with the same models as the other sources."""
    if not response['results']:
        return {**response, 'rankingStatus': 'empty'}
    try:
        results = get_candidate_ranker().rank(response['query'], response['results'])
    except Exception as error:
        logger.warning('Shop result ranking failed (%s).', type(error).__name__, exc_info=True)
        notice = "Our search models are unavailable. Showing the shops' original order. Please try again shortly."
        return {**response, 'rankingStatus': 'unavailable', 'warningCode': 'shops_ranking_unavailable',
                'warning': ' '.join(filter(None, [response.get('warning'), notice]))}
    return {**response, 'results': results, 'searchMode': 'online-shops-semantic-reranked',
            'semanticModel': 'fine-tuned', 'rankingStatus': 'ranked'}

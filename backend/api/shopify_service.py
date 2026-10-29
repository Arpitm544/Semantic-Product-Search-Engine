"""Shopify search over immutable generations with live selling details."""
import json
from functools import lru_cache
from threading import Lock
from urllib.parse import urlparse
import numpy as np
from src.data.db import get_database
from src.data.shopify_repository import Repository
from src.integrations.shopify.config import Settings
from src.integrations.shopify.client import Client
from src.integrations.shopify.hydration import hydrate
from src.search.shopify_index import root, SemanticIndex
from src.semantic.identity import vector_generation
from src.config import PROJECT_ROOT
import os
from src.search.product_search import ProductSearch
from api.ranking_service import get_candidate_ranker

_engines = {}
_lock = Lock()


@lru_cache(maxsize=1)
def database():
    return get_database()


def context():
    settings = Settings().validate()
    return settings, Repository(database(), settings.shop)


def status():
    try:
        settings, repository = context()
        state = repository.state.find_one({'_id': settings.shop}) or {}
        return {'enabled': True, 'status': 'degraded' if state.get('error') else 'ready' if state.get('generation') else 'initial_sync',
                'productCount': state.get('count', 0), 'lastSuccess': state.get('last_success'), 'error': state.get('error')}
    except ValueError:
        return {'enabled': False, 'status': 'disabled', 'productCount': 0}


def engine(settings):
    directory = root(settings.shop)
    if not (directory / 'current.json').exists():
        raise ValueError('Shopify is awaiting its first successful sync. Run sync_shopify.py.')
    manifest = json.loads((directory / 'current.json').read_text())
    model_path = str((PROJECT_ROOT / os.getenv('SEMANTIC_MODEL_PATH', 'models/colab-export/esci-minilm-20k')).resolve())
    if manifest.get('model') != vector_generation(model_path, 'shopify'):
        raise ValueError('Shopify model changed. Run sync_shopify.py before searching.')
    generation = manifest['generation']
    if not generation.isalnum():
        raise ValueError('Invalid Shopify generation.')
    with _lock:
        if _engines.get(settings.shop, (None,))[0] == generation:
            return _engines[settings.shop][1]
        target = directory / 'generations' / generation
        products = json.loads((target / 'products.json').read_text())
        ranker = get_candidate_ranker()
        vectors = np.load(target / 'vectors.npy', allow_pickle=False)
        semantic = SemanticIndex(products, vectors, ranker.encoder)
        result = ProductSearch(products, semantic, ranker.reranker, model_lock=ranker.lock) if products else None
        _engines[settings.shop] = (generation, result)
        return result


def https_url(value):
    parsed = urlparse(value or '')
    return value if parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password else None


def search(query, fuzzy=True):
    settings, repository = context()
    active = engine(settings)
    if active is None:
        return {'query': query, 'results': [], 'candidateCount': 0, 'source': 'shopify'}
    response = active.search(query, limit=60, fuzzy=fuzzy)
    candidates = response['results']
    eligible = {r['product_gid'] for r in repository.products.find(
        {'shop_domain': settings.shop, 'eligible': True, 'product_gid': {'$in': [p['product_gid'] for p in candidates]}},
        {'product_gid': 1})}
    candidates = [p for p in candidates if p['product_gid'] in eligible]
    details = hydrate(Client(settings), [p['product_gid'] for p in candidates])
    results = []
    for product in candidates:
        detail = details.get(product['product_gid'])
        if not detail or not https_url(detail.get('onlineStoreUrl')):
            continue
        low = detail['priceRange']['minVariantPrice']
        high = detail['priceRange']['maxVariantPrice']
        results.append({k: product[k] for k in ('id', 'title', 'category', 'brand', 'description', 'score', 'matchSources')})
        results[-1].update(source='shopify', merchant=settings.shop, url=detail['onlineStoreUrl'],
                          title=detail['title'], imageUrl=https_url((detail.get('featuredImage') or {}).get('url')),
                          currency=low['currencyCode'], price=low['amount'],
                          priceLabel=f"{low['currencyCode']} {low['amount']}" + (f"–{high['amount']}" if high['amount'] != low['amount'] else ''),
                          availableForSale=detail['availableForSale'], detailsStatus='current')
        if len(results) == 20:
            break
    return {**response, 'results': results, 'source': 'shopify'}

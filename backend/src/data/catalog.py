"""MongoDB is the sole serving source for product records."""
import os
from functools import lru_cache
from threading import Lock
from src.data.db import get_database

COLLECTION = os.getenv('MONGO_COLLECTION', 'amazon_products')
_products_lock = Lock()
_products_signature = None
_products_cache = None

class CatalogUpdatingError(ValueError):
    """The catalog is temporarily unavailable while an import is published."""


@lru_cache(maxsize=1)
def database():
    """Reuse one MongoDB connection for catalog requests."""
    return get_database()

def version():
    """Read the import record and ensure the catalog is ready."""
    manifest = database()['catalog_manifests'].find_one({'_id': COLLECTION})
    if manifest and manifest.get('status') == 'importing':
        raise CatalogUpdatingError('Amazon catalog import is in progress.')
    if not manifest or manifest.get('status') != 'ready':
        raise ValueError('MongoDB catalog is not ready. Run scripts/import_catalog.py.')
    return manifest

def load_products():
    """Return the verified catalog in ID order, shared until its manifest changes.

    Treat the returned list and its product records as read-only. Callers that
    need to sort or enrich records must create their own copies first.
    """
    with _products_lock:
        return _load_products()


def _load_products():
    global _products_signature, _products_cache
    manifest = version()
    signature = (COLLECTION, manifest.get('sha256'), manifest.get('updated_at'),
                 manifest.get('import_id'), manifest['product_count'])
    if manifest.get('sha256') and signature == _products_signature:
        return _products_cache
    products = list(database()[COLLECTION].find({}, {'_id': 0}).sort('id', 1))
    if version() != manifest:
        raise CatalogUpdatingError('MongoDB catalog changed while loading; retry after the import completes.')
    if len(products) != manifest['product_count']:
        raise ValueError('MongoDB catalog count differs from its manifest; reimport the catalog.')
    if manifest.get('sha256'):
        _products_signature, _products_cache = signature, products
    return products

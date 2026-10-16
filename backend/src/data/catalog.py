"""MongoDB is the sole serving source for product records."""
import os
from functools import lru_cache
from src.data.db import get_database

COLLECTION = os.getenv('MONGO_COLLECTION', 'amazon_products')

@lru_cache(maxsize=1)
def database():
    """Reuse one MongoDB connection for catalog requests."""
    return get_database()

def version():
    """Read the import record and ensure the catalog is ready."""
    manifest = database()['catalog_manifests'].find_one({'_id': COLLECTION})
    if not manifest or manifest.get('status') != 'ready':
        raise ValueError('MongoDB catalog is not ready. Run scripts/import_catalog.py.')
    return manifest

def load_products():
    """Load products in ID order and verify the import count."""
    manifest = version()
    products = list(database()[COLLECTION].find({}, {'_id': 0}).sort('id', 1))
    if len(products) != manifest['product_count']:
        raise ValueError('MongoDB catalog count differs from its manifest; reimport the catalog.')
    return products

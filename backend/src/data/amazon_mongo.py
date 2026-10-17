"""MongoDB is the sole serving source for Amazon product records."""
import os
from functools import lru_cache
from src.data.db import get_database

COLLECTION = os.getenv('MONGO_AMAZON_COLLECTION', 'amazon_products')

class CatalogUpdatingError(ValueError):
    """The catalog is temporarily unavailable while an import is published."""


@lru_cache(maxsize=1)
def database():
    return get_database()

def version():
    manifest = database()['catalog_manifests'].find_one({'_id': COLLECTION})
    if manifest and manifest.get('status') == 'importing':
        raise CatalogUpdatingError('Amazon catalog import is in progress.')
    if not manifest or manifest.get('status') != 'ready':
        raise ValueError('Amazon MongoDB catalog is not ready. Run scripts/import_amazon_mongo.py.')
    return manifest

def load_products():
    manifest = version()
    products = list(database()[COLLECTION].find({}, {'_id': 0}).sort('id', 1))
    if version() != manifest:
        raise CatalogUpdatingError('MongoDB catalog changed while loading; retry after the import completes.')
    if len(products) != manifest['product_count']:
        raise ValueError('MongoDB catalog count differs from its manifest; reimport the catalog.')
    return products

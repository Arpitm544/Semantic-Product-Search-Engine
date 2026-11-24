"""MongoDB is the sole serving source for product records."""
import os
import re
from functools import lru_cache
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit
import logging
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


_ASIN = re.compile(r'[A-Z0-9]{10}')


def amazon_url(product_id):
    """Link to a catalog product's Amazon page, from its ESCI id ("esci:us:<ASIN>").

    Only US ids with a well-formed ASIN get a link; anything else returns None.
    """
    parts = str(product_id or '').split(':')
    if len(parts) == 3 and parts[0] == 'esci' and parts[1] == 'us' and _ASIN.fullmatch(parts[2]):
        return f'https://www.amazon.com/dp/{parts[2]}'
    return None


IMAGES_COLLECTION = os.getenv('CATALOG_IMAGES_COLLECTION', 'catalog_images')
IMAGE_HOSTS = frozenset({'m.media-amazon.com'})
IMAGES_REFRESH_SECONDS = 600
_images_lock = Lock()
_images_cache = None  # (loaded_at, {product id: image url})
logger = logging.getLogger(__name__)


def safe_image_url(value):
    """Only https links on the allowed image hosts are served to the browser."""
    try:
        parts = urlsplit(str(value or ''))
    except ValueError:
        return None
    return value if parts.scheme == 'https' and parts.hostname in IMAGE_HOSTS else None


_SIZE_CODE = re.compile(r'\._[A-Za-z0-9,_]+_\.(jpg|jpeg|png)$')
_EXTENSION = re.compile(r'\.(jpg|jpeg|png)$')


def sized_image_url(url, pixels=300):
    """Ask Amazon's image server for a smaller version via its size code
    (e.g. "._SL1500_.jpg" -> "._SL300_.jpg"): about 7x lighter for thumbnails."""
    sized = _SIZE_CODE.sub(rf'._SL{pixels}_.\1', url)
    return sized if sized != url else _EXTENSION.sub(rf'._SL{pixels}_.\1', url)


def catalog_images():
    """Product photos imported by scripts/import_catalog_images.py, refreshed every
    ten minutes. Photos are optional: if they can't be read, results keep their
    illustrations and search carries on."""
    global _images_cache
    with _images_lock:
        if _images_cache and monotonic() - _images_cache[0] < IMAGES_REFRESH_SECONDS:
            return _images_cache[1]
        try:
            rows = database()[IMAGES_COLLECTION].find({}, {'_id': 1, 'image_url': 1})
            images = {row['_id']: url for row in rows if (url := safe_image_url(row.get('image_url')))}
        except Exception:
            logger.warning('Catalog photos are unavailable; showing illustrations.', exc_info=True)
            images = _images_cache[1] if _images_cache else {}
        _images_cache = (monotonic(), images)
        return images


def with_product_links(payload):
    """Add an Amazon link and, where one was imported, a real photo to catalog results."""
    images = catalog_images()
    results = []
    for item in payload.get('results', []):
        extra = {}
        if not item.get('url') and (link := amazon_url(item.get('id'))):
            extra['url'] = link
        if not item.get('imageUrl') and (image := images.get(item.get('id'))):
            extra['imageUrl'] = sized_image_url(image)
        results.append({**item, **extra} if extra else item)
    return {**payload, 'results': results}

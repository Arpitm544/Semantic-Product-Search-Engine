"""Independent Shopify and WooCommerce stores, read through their public product data.

No keys or approval are needed. Stores are listed in SHOP_STORES as
`platform:host[:CURRENCY]` entries, for example:

    SHOP_STORES=shopify:www.example-store.in:INR,woocommerce:shop.example.com

- Shopify: the public `/products.json` catalog is downloaded (up to
  SHOP_STORE_MAX_PRODUCTS products) and refreshed every six hours, then searched
  locally by keyword. Shopify's default robots.txt disallows `/search`, so the
  storefront search pages are never used. Shopify's catalog has no currency, so
  it comes from the entry (default INR).
- WooCommerce: searched live through the public Store API
  (`/wp-json/wc/store/v1/products?search=`), which reports its own currency.

Every request first checks the store's robots.txt and is skipped if disallowed.
Requests identify themselves with a generic user agent and never carry user data.
"""
from dataclasses import dataclass
import html
import logging
import os
import re
from threading import Lock
from time import monotonic
from urllib.robotparser import RobotFileParser

import requests

from api.shop_providers.base import DailyBudget, ProviderError, TIMEOUT, get_json, product
from src.keyword_search.bm25 import fit_bm25, search_bm25, tokenize
from src.search.typos import STOP_WORDS

USER_AGENT = 'SemanticProductSearch/1.0 (product search; respects robots.txt)'
HEADERS = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
PLATFORMS = ('shopify', 'woocommerce')
MAX_STORES = 20
SNAPSHOT_SECONDS = 6 * 3600
ROBOTS_SECONDS = 24 * 3600
SHOPIFY_PAGE_SIZE = 250
# Real public domain names only: no IP addresses, localhost, ports, or paths.
HOST = re.compile(r'^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$')


@dataclass(frozen=True)
class StoreConfig:
    platform: str
    host: str
    currency: str


def parse_stores(value):
    """Parse SHOP_STORES. Returns (stores, errors); invalid entries are skipped."""
    stores, errors, seen = [], [], set()
    for raw in (value or '').split(','):
        entry = raw.strip()
        if not entry:
            continue
        parts = [part.strip() for part in entry.split(':')]
        platform = parts[0].lower()
        host = parts[1].lower() if len(parts) > 1 else ''
        currency = parts[2].upper() if len(parts) > 2 and parts[2] else 'INR'
        if (platform not in PLATFORMS or len(parts) > 3 or not HOST.fullmatch(host)
                or not re.fullmatch(r'[A-Z]{3}', currency)):
            errors.append(entry)
            continue
        if host in seen:
            continue
        seen.add(host)
        stores.append(StoreConfig(platform, host, currency))
    if len(stores) > MAX_STORES:
        errors.extend(f'{store.platform}:{store.host}' for store in stores[MAX_STORES:])
        stores = stores[:MAX_STORES]
    return stores, errors


def max_products():
    try:
        return max(1, min(5000, int(os.environ.get('SHOP_STORE_MAX_PRODUCTS', '1000'))))
    except ValueError:
        return 1000


def plain_text(value, limit=2000):
    text = re.sub(r'<[^>]+>', ' ', value) if isinstance(value, str) else ''
    return re.sub(r'\s+', ' ', html.unescape(text)).strip()[:limit]


class Robots:
    """robots.txt rules for one host, cached for a day."""

    def __init__(self, host):
        self.host = host
        self._lock = Lock()
        self._parser = None
        self._fetched = 0.0

    def allowed(self, path):
        with self._lock:
            if self._parser is None or monotonic() - self._fetched > ROBOTS_SECONDS:
                self._parser = self._load()
                self._fetched = monotonic()
            return self._parser.can_fetch(USER_AGENT, f'https://{self.host}{path}')

    def _load(self):
        parser = RobotFileParser()
        status, text = fetch_robots(self.host)
        if status in (401, 403):
            parser.disallow_all = True
        elif status >= 500:
            raise ProviderError(f'{self.host} is unavailable right now.', 'unavailable')
        elif status == 200:
            parser.parse(text.splitlines())
        else:
            # 404 and other missing robots.txt files allow everything.
            parser.allow_all = True
        return parser


def fetch_robots(host):
    """Return (status, text) for a host's robots.txt."""
    try:
        response = requests.get(f'https://{host}/robots.txt', headers={'User-Agent': USER_AGENT},
                                timeout=TIMEOUT, allow_redirects=False)
    except requests.RequestException:
        raise ProviderError(f'Cannot reach {host} right now.', 'unavailable') from None
    with response:
        return response.status_code, response.text if response.status_code == 200 else ''


def keyword_query(query):
    """Drop filler words such as "with" so they don't match unrelated products."""
    words = [word for word in tokenize(query) if word not in STOP_WORDS]
    return ' '.join(words) or query


def shopify_product(store, row):
    if not isinstance(row, dict) or not row.get('handle'):
        return None
    variants = [v for v in row.get('variants') or [] if isinstance(v, dict)]
    prices = []
    for variant in variants:
        try:
            prices.append(float(variant.get('price')))
        except (TypeError, ValueError):
            pass
    available = [v.get('available') for v in variants if isinstance(v.get('available'), bool)]
    images = [image.get('src') for image in row.get('images') or [] if isinstance(image, dict)]
    tags = row.get('tags')
    tags = tags if isinstance(tags, list) else [tag.strip() for tag in str(tags or '').split(',')]
    result = product(provider=f'store:{store.host}', merchant=store.host, identity=row.get('id'),
                     title=html.unescape(str(row.get('title') or '')), description=plain_text(row.get('body_html')),
                     price=min(prices) if prices else None, currency=store.currency,
                     image=images[0] if images else None, url=f"https://{store.host}/products/{row['handle']}",
                     brand=row.get('vendor'), category=row.get('product_type'),
                     in_stock=any(available) if available else None,
                     attributes=[tag for tag in tags if isinstance(tag, str)][:10])
    if result:
        result['matchSources'] = ['store']
    return result


def woocommerce_product(store, row):
    if not isinstance(row, dict):
        return None
    prices = row.get('prices') if isinstance(row.get('prices'), dict) else {}
    amount, currency = None, prices.get('currency_code') or store.currency
    try:
        amount = int(prices.get('price')) / (10 ** int(prices.get('currency_minor_unit', 2)))
    except (TypeError, ValueError):
        pass
    images = [image.get('src') for image in row.get('images') or [] if isinstance(image, dict)]
    categories = [c.get('name') for c in row.get('categories') or [] if isinstance(c, dict) and c.get('name')]
    brands = [b.get('name') for b in row.get('brands') or [] if isinstance(b, dict) and b.get('name')]
    result = product(provider=f'store:{store.host}', merchant=store.host, identity=row.get('id'),
                     title=html.unescape(str(row.get('name') or '')),
                     description=plain_text(row.get('short_description') or row.get('description')),
                     price=amount, currency=currency, image=images[0] if images else None,
                     url=row.get('permalink'), brand=html.unescape(brands[0]) if brands else None,
                     category=html.unescape(categories[0]) if categories else None,
                     in_stock=row.get('is_in_stock'))
    if result:
        result['matchSources'] = ['store']
    return result


class StoreProvider:
    """One configured store, searched like any other online shop."""

    def __init__(self, config):
        self.config = config
        self.NAME = f'store:{config.host}'
        self.LABEL = config.host
        self.robots = Robots(config.host)
        self.budget = DailyBudget('SHOP_STORE_DAILY_CALLS', 2000)
        self._lock = Lock()
        self._snapshot = None  # (fetched_at, keyword index)

    def configured(self):
        return True

    def _get(self, path, expect=dict, **params):
        if not self.robots.allowed(path):
            raise ProviderError(f'{self.LABEL} does not allow automated access to its products (robots.txt).', 'blocked')
        if not self.budget.take():
            raise ProviderError(f'{self.LABEL} daily request limit reached. Try again tomorrow.', 'quota')
        return get_json(f'https://{self.config.host}{path}', self.LABEL, expect=expect,
                        params=params, headers=HEADERS)

    def search(self, query, limit):
        if self.config.platform == 'woocommerce':
            rows = self._get('/wp-json/wc/store/v1/products', expect=list,
                             search=query, per_page=str(max(1, min(limit, 20))))
            return [p for p in (woocommerce_product(self.config, row) for row in rows) if p][:limit]
        index = self._shopify_index()
        return [entry['product'] for entry, _ in search_bm25(index, keyword_query(query), limit)]

    def _shopify_index(self):
        with self._lock:
            if self._snapshot and monotonic() - self._snapshot[0] < SNAPSHOT_SECONDS:
                return self._snapshot[1]
            products, seen_ids, page, cap = [], set(), 1, max_products()
            while len(products) < cap:
                payload = self._get('/products.json', limit=str(SHOPIFY_PAGE_SIZE), page=str(page))
                rows = payload.get('products')
                if not isinstance(rows, list):
                    raise ProviderError(f'{self.LABEL} returned an invalid response.', 'invalid_response')
                added = 0
                for row in rows:
                    product = shopify_product(self.config, row)
                    if product and product['id'] not in seen_ids:
                        seen_ids.add(product['id'])
                        products.append(product)
                        added += 1
                if len(rows) < SHOPIFY_PAGE_SIZE or added == 0:
                    break
                page += 1
            documents = [{'product': p, 'representation_text': ' '.join(filter(None, [
                p['title'], p.get('brand'), p.get('category'), ' '.join(p['attributes']), p['description'][:500]]))}
                for p in products[:cap]]
            index = fit_bm25(documents)
            self._snapshot = (monotonic(), index)
            return index


_providers = {}
_providers_lock = Lock()
_warned = set()
logger = logging.getLogger(__name__)


def configured_stores():
    """Providers for SHOP_STORES, reused so snapshots and robots rules stay cached."""
    stores, errors = parse_stores(os.environ.get('SHOP_STORES', ''))
    for entry in errors:
        if entry not in _warned:
            _warned.add(entry)
            logger.warning('Ignoring SHOP_STORES entry %r: use platform:host[:CURRENCY] with shopify or '
                           'woocommerce and a public domain name (at most %d stores).', entry, MAX_STORES)
    with _providers_lock:
        result = []
        for config in stores:
            if _providers.get(config.host) is None or _providers[config.host].config != config:
                _providers[config.host] = StoreProvider(config)
            result.append(_providers[config.host])
        return result

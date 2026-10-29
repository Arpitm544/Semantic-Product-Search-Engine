"""Reconcile one bounded collection. Publish only after a complete scoped scan."""
import uuid
from datetime import timedelta
from .client import Client
from .queries import COLLECTION, DETAILS
from .mapper import map_product
from src.data.shopify_repository import now
from src.search.shopify_index import build, root, atomic_json
from pymongo.errors import DuplicateKeyError


def synchronize(settings, repository, ranker):
    # Unique _id plus lease prevents overlapping workers/manual syncs.
    owner = uuid.uuid4().hex
    key = f'lock:{settings.shop}'
    try:
        repository.state.find_one_and_update(
            {'_id': key, '$or': [{'lease_until': {'$lt': now()}}, {'owner': owner}]},
            {'$set': {'owner': owner, 'lease_until': now() + timedelta(minutes=30)}}, upsert=True)
    except DuplicateKeyError as error:
        raise RuntimeError('Another Shopify sync is running.') from error
    client = Client(settings)
    state_key = settings.shop
    try:
        products, after = [], None
        while True:
            data = client.query(COLLECTION, {'id': settings.collection, 'after': after})
            collection = data.get('collection')
            if collection is None:
                raise ValueError('Shopify collection is unavailable; existing products preserved.')
            page = collection['products']
            products.extend(page['nodes'])
            if len(products) > settings.cap or (len(products) == settings.cap and page['pageInfo']['hasNextPage']):
                raise ValueError('Collection exceeds the product cap. Choose a smaller collection or raise the cap.')
            if not page['pageInfo']['hasNextPage']:
                break
            cursor = page['pageInfo']['endCursor']
            if not cursor or cursor == after:
                raise ValueError('Shopify pagination did not advance.')
            after = cursor
        visible = set()
        for offset in range(0, len(products), 100):
            nodes = client.query(DETAILS, {'ids': [p['id'] for p in products[offset:offset + 100]]}, storefront=True)['nodes']
            visible.update(n['id'] for n in nodes if n and n.get('onlineStoreUrl'))
        generation = uuid.uuid4().hex
        records = []
        for product in products:
            record = map_product(product, settings.shop)
            record['eligible'] = record['eligible'] and record['product_gid'] in visible
            record.update(sync_generation=generation, synced_at=now().isoformat())
            records.append(record)
        # Build first: model/index failures never replace serving product state.
        eligible = sorted([r for r in records if r['eligible']], key=lambda r: r['id'])
        # Renew and verify ownership before expensive index work.
        renewed = repository.state.update_one({'_id': key, 'owner': owner},
                    {'$set': {'lease_until': now() + timedelta(hours=2)}})
        if not renewed.matched_count:
            raise RuntimeError('Shopify sync lease lost.')
        index_manifest = build(eligible, settings.shop, ranker)
        for record in records:
            repository.products.replace_one({'shop_domain': settings.shop, 'product_gid': record['product_gid']}, record, upsert=True)
        repository.products.delete_many({'shop_domain': settings.shop, 'sync_generation': {'$ne': generation}})
        atomic_json(root(settings.shop) / 'current.json', index_manifest)
        repository.state.update_one({'_id': state_key}, {'$set': {'last_success': now(), 'count': len(eligible),
             'generation': index_manifest['generation'], 'error': None}}, upsert=True)
        return len(eligible)
    except Exception:
        repository.state.update_one({'_id': state_key}, {'$set': {'error': 'Sync failed; check worker logs.'}}, upsert=True)
        raise
    finally:
        repository.state.delete_one({'_id': key, 'owner': owner})

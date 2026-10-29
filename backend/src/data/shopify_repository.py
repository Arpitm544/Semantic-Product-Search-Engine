"""Dedicated Shopify collections; no writes to the Amazon catalog."""
from datetime import datetime, timezone, timedelta
from pymongo import ReturnDocument


def now():
    return datetime.now(timezone.utc)


class Repository:
    def __init__(self, db, shop):
        self.db, self.shop = db, shop
        self.products = db.shopify_products
        self.jobs = db.shopify_jobs
        self.state = db.shopify_sync_state

    def setup(self):
        self.products.create_index([('shop_domain', 1), ('product_gid', 1)], unique=True)
        self.jobs.create_index('delivery', unique=True)
        self.jobs.create_index([('status', 1), ('next_attempt', 1)])
        self.jobs.create_index('expires_at', expireAfterSeconds=0)

    def enqueue(self, delivery):
        self.jobs.update_one({'delivery': f'{self.shop}:{delivery}'}, {'$setOnInsert': {
            'shop_domain': self.shop, 'created_at': now(), 'status': 'pending', 'next_attempt': now(), 'attempts': 0}}, upsert=True)

    def claim(self):
        return self.jobs.find_one_and_update({'shop_domain': self.shop, '$or': [
            {'status': 'pending', 'next_attempt': {'$lte': now()}},
            {'status': 'running', 'lease_until': {'$lt': now()}}]},
            {'$set': {'status': 'running', 'lease_until': now() + timedelta(minutes=20)},
             '$inc': {'attempts': 1}}, return_document=ReturnDocument.AFTER)

    def finish(self, job, error=False):
        values = {'status': 'failed' if error and job['attempts'] >= 5 else 'pending' if error else 'done'}
        if error:
            values['next_attempt'] = now() + timedelta(seconds=min(900, 2 ** job['attempts']))
            values['error'] = 'Sync failed; inspect worker logs and retry.'
        else:
            values['expires_at'] = now() + timedelta(days=7)
        self.jobs.update_one({'_id': job['_id'], 'attempts': job['attempts']}, {'$set': values})

    def snapshot(self):
        return list(self.products.find({'shop_domain': self.shop, 'eligible': True}, {'_id': 0}).sort('id', 1))

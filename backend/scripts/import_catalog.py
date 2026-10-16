"""Import prepared Amazon JSON into a dedicated MongoDB collection; never deletes data."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pymongo import ReplaceOne
from src.data.catalog import database, COLLECTION
from src.config import DATASET_DIR


def parse_arguments():
    """Read options supplied after the command name."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DATASET_DIR/'prepared/products.json')
    return parser.parse_args()


def read_products(source):
    """Read the prepared catalog and reject duplicate or unexpected IDs."""
    raw = source.read_bytes()
    products = json.loads(raw)
    ids = [p['id'] for p in products]
    if len(ids) != len(set(ids)) or not all(str(pid).startswith('esci:') for pid in ids):
        raise ValueError('Expected unique Amazon ESCI product IDs.')
    return raw, products, ids


def import_products(source):
    """Write batches to MongoDB and mark the catalog ready after validation."""
    raw, products, ids = read_products(source)
    manifest = {'product_count': len(products), 'sha256': hashlib.sha256(raw).hexdigest(),
                'source': 'Amazon ESCI prepared catalog', 'updated_at': datetime.now(timezone.utc).isoformat()}
    db = database()
    db.client.admin.command('ping')
    collection = db[COLLECTION]
    collection.create_index('id', unique=True)
    existing_ids = set(collection.distinct('id'))
    if existing_ids - set(ids):
        raise ValueError('Collection contains other products. Choose a new MONGO_COLLECTION.')
    db['catalog_manifests'].replace_one({'_id': COLLECTION}, {'_id': COLLECTION, **manifest, 'status': 'importing'}, upsert=True)
    for offset in range(0, len(products), 500):
        collection.bulk_write([ReplaceOne({'id': p['id']}, p, upsert=True) for p in products[offset:offset+500]], ordered=False)
    if collection.count_documents({}) != len(products):
        raise ValueError('Import count mismatch.')
    db['catalog_manifests'].replace_one({'_id': COLLECTION}, {'_id': COLLECTION, **manifest, 'status': 'ready'})
    print(f'Imported {len(products):,} Amazon products into {db.name}.{COLLECTION}')


def main():
    args = parse_arguments()
    import_products(args.source)


if __name__ == "__main__":
    main()

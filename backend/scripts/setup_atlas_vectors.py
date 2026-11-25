"""Upload catalog embeddings and create an Atlas vector index. Run after import_catalog.py."""
import argparse
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pymongo import ReplaceOne
from pymongo.operations import SearchIndexModel
from src.config import PROJECT_ROOT
from src.data.catalog import database, load_products, version
from src.semantic.atlas_search import collection_name, definition_matches, index_definition, index_name
from src.semantic.identity import vector_generation
from scripts.import_catalog import catalog_import_lock


def prune_old_generations(db, active_generation):
    """Drop stale product_vectors_* collections and manifests after a new generation is ready."""
    prefix = collection_name('')
    active_col = collection_name(active_generation)
    dropped = []
    for name in db.list_collection_names():
        if name.startswith(prefix) and name != active_col:
            db.drop_collection(name)
            dropped.append(name)
    db['vector_manifests'].delete_many({'_id': {'$ne': active_generation}})
    if dropped:
        print(f'Pruned {len(dropped)} old vector collection(s): {", ".join(sorted(dropped))}')


def setup(timeout=900, keep_old=False):
    from sentence_transformers import SentenceTransformer
    import numpy as np

    db = database()
    db.client.admin.command('ping')
    with catalog_import_lock(db):
        manifest = version()
        products = load_products()
        model_path = str((PROJECT_ROOT / os.getenv(
            'SEMANTIC_MODEL_PATH', 'models/colab-export/esci-minilm-20k')).resolve())
        generation = vector_generation(model_path, manifest['sha256'])
        model = SentenceTransformer(model_path, local_files_only=True, device='cpu')
        dimensions = model.get_sentence_embedding_dimension()
        definition = index_definition(dimensions)
        collection = db[collection_name(generation)]
        collection.create_index('id', unique=True)
        metadata = db['vector_manifests']
        previous = metadata.find_one({'_id': generation})
        if not previous or previous.get('status') != 'ready':
            metadata.replace_one({'_id': generation}, {'_id': generation, 'status': 'building'}, upsert=True)
            for start in range(0, len(products), 128):
                batch = products[start:start + 128]
                vectors = np.asarray(model.encode(
                    [p.get('representation_text') or p.get('title', '') for p in batch],
                    normalize_embeddings=True, show_progress_bar=False, batch_size=32))
                if vectors.shape != (len(batch), dimensions) or not np.isfinite(vectors).all():
                    raise ValueError('Encoder produced invalid embeddings.')
                collection.bulk_write([ReplaceOne({'id': p['id']},
                    {'id': p['id'], 'embedding': v.tolist()}, upsert=True)
                    for p, v in zip(batch, vectors)], ordered=False)
                print(f'Uploaded {min(start + 128, len(products))}/{len(products)}', flush=True)
        if collection.count_documents({}) != len(products) or version() != manifest:
            raise RuntimeError('Catalog changed or vector count differs. Rerun setup.')
        indexes = list(collection.list_search_indexes(name=index_name()))
        if not indexes:
            collection.create_search_index(model=SearchIndexModel(
                definition=definition, name=index_name(), type='vectorSearch'))
        elif not definition_matches(indexes[0].get('latestDefinition'), dimensions):
            raise RuntimeError('Existing index definition differs. Choose another ATLAS_VECTOR_INDEX name.')
        deadline = time.monotonic() + timeout
        while True:
            indexes = list(collection.list_search_indexes(name=index_name()))
            if indexes and indexes[0].get('status') == 'FAILED':
                raise RuntimeError('Atlas index build failed. Inspect it in the Atlas console.')
            if indexes and indexes[0].get('queryable'):
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('Atlas index is still building. Rerun setup later.')
            time.sleep(5)
        metadata.replace_one({'_id': generation}, {
            '_id': generation, 'status': 'ready', 'product_count': len(products),
            'dimensions': dimensions, 'catalog_sha256': manifest['sha256'],
        }, upsert=True)
        if not keep_old:
            prune_old_generations(db, generation)
        print(f'Atlas vector index ready: {db.name}.{collection.name} / {index_name()}')
        print('Atlas indexing is eventually consistent; newly uploaded vectors may take time to appear.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=int, default=900, help='Index readiness timeout in seconds')
    parser.add_argument('--keep-old', action='store_true', help='Keep previous product_vectors_* generations')
    args = parser.parse_args()
    setup(args.timeout, keep_old=args.keep_old)

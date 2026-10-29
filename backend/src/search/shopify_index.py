"""Immutable local cosine index. Keeps Shopify independent of Atlas setup."""
import hashlib
import json
import os
import uuid
from pathlib import Path
import numpy as np
from src.config import PROJECT_ROOT
from src.semantic.identity import vector_generation


def root(shop):
    return PROJECT_ROOT / 'indexes' / 'shopify' / shop


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{uuid.uuid4().hex}.tmp')
    temporary.write_text(json.dumps(value))
    temporary.replace(path)


def build(products, shop, ranker):
    directory = root(shop)
    model = str((PROJECT_ROOT / os.getenv('SEMANTIC_MODEL_PATH', 'models/colab-export/esci-minilm-20k')).resolve())
    fingerprint = vector_generation(model, 'shopify')
    cache = directory / 'embeddings'
    cache.mkdir(parents=True, exist_ok=True)
    vectors = []
    for product in products:
        key = hashlib.sha256((product['text_hash'] + fingerprint).encode()).hexdigest()
        path = cache / f'{key}.npy'
        vector = None
        if path.exists():
            try:
                vector = np.load(path, allow_pickle=False)
                if vector.ndim != 1 or not np.isfinite(vector).all():
                    vector = None
            except (OSError, ValueError):
                pass
        if vector is None:
            with ranker.lock:
                vector = np.asarray(ranker.encoder.encode([product['representation_text']],
                                    normalize_embeddings=True, convert_to_numpy=True))[0].astype('float32')
            if vector.ndim != 1 or not np.isfinite(vector).all():
                raise ValueError('Invalid Shopify embedding.')
            temporary = cache / f'.{uuid.uuid4().hex}.npy'
            np.save(temporary, vector, allow_pickle=False)
            temporary.replace(path)
        vectors.append(vector)
    generation = uuid.uuid4().hex
    target = directory / 'generations' / generation
    target.mkdir(parents=True)
    np.save(target / 'vectors.npy', np.stack(vectors) if vectors else np.empty((0, 0), dtype='float32'), allow_pickle=False)
    atomic_json(target / 'products.json', products)
    return {'generation': generation, 'count': len(products), 'model': fingerprint}


class SemanticIndex:
    def __init__(self, products, vectors, encoder):
        self.products, self.vectors, self.encoder = products, vectors, encoder
        self.model_name = 'shopify-local-cosine'
        if len(products) != len(vectors) or vectors.ndim != 2 or not np.isfinite(vectors).all():
            raise ValueError('Invalid Shopify index generation.')

    def search(self, query, top_k=10):
        vector = np.asarray(self.encoder.encode([query], normalize_embeddings=True, convert_to_numpy=True))[0]
        scores = self.vectors @ vector
        return [(self.products[i], float(scores[i])) for i in np.argsort(-scores, kind='stable')[:top_k]]

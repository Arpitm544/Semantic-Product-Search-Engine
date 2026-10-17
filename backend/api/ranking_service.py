"""Share local search models between the MongoDB index and shopping candidates."""

import os
from threading import Lock

from src.config import PROJECT_ROOT
from src.search.ranking import blend_ranks

_ranker = None
_signature = None
_load_lock = Lock()


class CandidateRanker:
    """Rank an external candidate list without changing the MongoDB index."""

    def __init__(self, encoder, reranker):
        self.encoder = encoder
        self.reranker = reranker
        self.lock = Lock()

    def rank(self, query, products):
        import numpy as np

        if not products:
            return []
        texts = [
            f"[Title] {product['title'][:512]}"
            + (f" | [Description] {product['description'][:2000]}" if product.get('description') else '')
            for product in products
        ]
        # Both search sources share this lock because they reuse the same models.
        with self.lock:
            vectors = np.asarray(self.encoder.encode(
                [query, *texts], normalize_embeddings=True, convert_to_numpy=True,
                batch_size=32, show_progress_bar=False,
            ))
            if vectors.ndim != 2 or vectors.shape[0] != len(products) + 1 or not np.isfinite(vectors).all():
                raise ValueError('Invalid product embeddings.')
            semantic_scores = vectors[1:] @ vectors[0]
            reranker_scores = np.asarray(self.reranker.predict(
                [(query, product_text) for product_text in texts],
                batch_size=32, show_progress_bar=False,
            )).reshape(-1)
            if len(reranker_scores) != len(products) or not np.isfinite(reranker_scores).all():
                raise ValueError('Invalid reranker scores.')

        # Use the same rank fusion weights as MongoDB search: 25% retrieval,
        # 75% cross-encoder reranking. Here retrieval order comes from our encoder.
        semantic_order = sorted(range(len(products)), key=lambda i: (-float(semantic_scores[i]), i))
        reranker_order = sorted(range(len(products)), key=lambda i: (-float(reranker_scores[i]), i))
        semantic_positions = {i: position for position, i in enumerate(semantic_order, 1)}
        reranker_positions = {i: position for position, i in enumerate(reranker_order, 1)}
        scores = blend_ranks(semantic_positions, reranker_positions)
        order = sorted(range(len(products)), key=lambda i: (-scores[i], semantic_positions[i], i))
        return [{
            **products[i],
            'providerRank': i + 1,
            'semanticScore': float(semantic_scores[i]),
            'rerankerScore': float(reranker_scores[i]),
            'score': scores[i],
            'matchSources': list(dict.fromkeys([*products[i].get('matchSources', []), 'semantic', 'reranker'])),
        } for i in order]


def get_candidate_ranker():
    """Load the configured local weights once, independently of MongoDB readiness."""
    global _ranker, _signature
    signature = tuple(str((PROJECT_ROOT / os.environ.get(name, default)).resolve()) for name, default in (
        ('SEMANTIC_MODEL_PATH', 'models/colab-export/esci-minilm-20k'),
        ('RERANKER_MODEL_PATH', 'models/ms-marco-MiniLM-L6-v2'),
    ))
    with _load_lock:
        if _ranker is not None and _signature == signature:
            return _ranker
        import torch
        from sentence_transformers import CrossEncoder, SentenceTransformer

        torch.set_num_threads(2)
        encoder = SentenceTransformer(signature[0], local_files_only=True, device='cpu')
        reranker = CrossEncoder(signature[1], local_files_only=True, device='cpu', max_length=256)
        _ranker = CandidateRanker(encoder, reranker)
        _signature = signature
        return _ranker

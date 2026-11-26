"""Tests for PipelineParams and exactness of cached Optuna replay."""

import numpy as np
import pytest

from src.evaluation.tuning import (
    LazyScoreStore,
    evaluate_cached,
    precompute_validation_data,
    replay_query,
)
from src.search.product_search import ProductSearch
from src.search.ranking import PipelineParams, configured_pipeline_params


PRODUCTS = [
    {"id": "p1", "title": "Wireless headphones", "representation_text": "wireless bluetooth headphones over ear"},
    {"id": "p2", "title": "Wired earbuds", "representation_text": "wired earbuds in ear audio"},
    {"id": "p3", "title": "Leather belt", "representation_text": "full grain leather belt brown"},
    {"id": "p4", "title": "Canvas belt", "representation_text": "canvas belt casual"},
    {"id": "p5", "title": "Running shoes", "representation_text": "running shoes lightweight"},
    {"id": "p6", "title": "Noise cancelling headphones", "representation_text": "noise cancelling headphones travel"},
    {"id": "p7", "title": "Headphones carrying case", "representation_text": "hard travel case for headphones"},
]


class LetterEncoder:
    def encode(self, texts, normalize_embeddings=True, **_):
        rows = []
        for text in texts:
            vector = np.zeros(26, dtype="float32")
            for char in text.lower():
                if "a" <= char <= "z":
                    vector[ord(char) - 97] += 1
            norm = np.linalg.norm(vector) or 1.0
            rows.append(vector / norm)
        return np.asarray(rows)


class FakeSemantic:
    def __init__(self, products):
        self.products = products
        self.encoder = LetterEncoder()
        self.vectors = self.encoder.encode([p["representation_text"] for p in products])

    def search(self, query, top_k=10):
        qvec = self.encoder.encode([query])[0]
        scores = self.vectors @ qvec
        top = sorted(range(len(self.products)), key=lambda i: (-float(scores[i]), i))[:top_k]
        return [(self.products[i], float(scores[i])) for i in top]


class FakeReranker:
    def predict(self, pairs, **_):
        return [
            len(set(q.lower().split()) & set(t.lower().split())) + 0.01 * len(t)
            for q, t in pairs
        ]


QUERIES = [
    {
        "query_id": "q1",
        "query": "headphones",
        "kind": "clean",
        "relevant_doc_ids": ["p1", "p6"],
        "grades": {"p1": 3, "p6": 3, "p7": 1},
    },
    {
        "query_id": "q2",
        "query": "headphnes",
        "kind": "deletion",
        "relevant_doc_ids": ["p1", "p6"],
        "grades": {"p1": 3, "p6": 3},
    },
    {
        "query_id": "q3",
        "query": "leather belt",
        "kind": "clean",
        "relevant_doc_ids": ["p3"],
        "grades": {"p3": 3, "p4": 2},
    },
]


@pytest.mark.parametrize("params", [
    PipelineParams(),
    PipelineParams(
        bm25_k=4,
        semantic_k=5,
        hybrid_rrf_k=15,
        semantic_weight=1.4,
        variation_limit=4,
        variation_rrf_k=20,
        original_variation_weight=1.3,
        corrected_variation_weight=0.8,
        alt_variation_weight=0.2,
        rerank_k=4,
        blend_rrf_k=12,
        retrieval_weight=0.3,
        reranker_weight=0.7,
    ),
])
def test_cached_replay_matches_live_product_search(params):
    semantic = FakeSemantic(PRODUCTS)
    reranker = FakeReranker()
    live = ProductSearch(PRODUCTS, semantic, reranker, params=params)

    cache = precompute_validation_data(
        PRODUCTS, semantic, reranker, QUERIES, max_stage_k=7, max_rerank_precompute=3,
    )
    by_id = {p["id"]: p for p in PRODUCTS}
    store = LazyScoreStore(by_id, reranker, cache["reranker_scores"])

    for entry in cache["queries"]:
        corrected, _ = live.spelling.correct(entry["query"])
        variations = live.spelling.alternatives(entry["query"])
        live_cands, _ = live.find_candidates(variations, entry["query"])
        live_ranked, _ = live.rank_candidates(corrected, live_cands)

        replay_hybrid, replay_ranked, cand_count = replay_query(
            entry, cache["bm25_lists"], cache["semantic_lists"], store, params,
        )
        assert replay_hybrid == live_cands[:10]
        assert replay_ranked == live_ranked[:10]
        expected_count = min(len(live_cands), params.rerank_k) if params.rerank_k else len(live_cands)
        assert cand_count == expected_count

    summary = evaluate_cached(cache, store, params)
    assert 0.0 <= summary["reranked"]["ndcg@10"] <= 1.0
    assert summary["mean_rerank_candidates"] > 0


def test_configured_pipeline_params_env_override_and_fallback(tmp_path, monkeypatch):
    import json

    custom = tmp_path / "custom.json"
    custom.write_text(json.dumps({"rerank_k": 25, "blend_rrf_k": 35}))
    monkeypatch.setenv("PIPELINE_PARAMS_PATH", str(custom))
    loaded = configured_pipeline_params()
    assert loaded.rerank_k == 25 and loaded.blend_rrf_k == 35

    monkeypatch.setenv("PIPELINE_PARAMS_PATH", str(tmp_path / "missing.json"))
    fallback = configured_pipeline_params()
    assert fallback == PipelineParams()



def test_paired_tuning_interval_is_zero_for_identical_runs():
    from scripts.tune_pipeline import METRIC_NAMES, compare_test_runs

    rows = [{"family": family, "stages": {"reranked": dict.fromkeys(METRIC_NAMES, score)}}
            for family, score in enumerate((0.0, 0.2, 0.8, 1.0))]
    result = compare_test_runs(rows, rows)["ndcg@10"]
    assert result == {"delta": 0.0, "confidenceInterval": [0.0, 0.0], "pValue": 1.0}


def test_tuning_cache_key_changes_with_relevance_labels(tmp_path):
    from scripts.tune_pipeline import validation_cache_key

    original = [{"query": "running shoes", "grades": {"shoe": 3}}]
    modified = [{"query": "running shoes", "grades": {"shoe": 0}}]
    encoder, reranker = tmp_path / "encoder", tmp_path / "reranker"
    assert validation_cache_key("catalog", encoder, reranker, original, 50, 30) != (
        validation_cache_key("catalog", encoder, reranker, modified, 50, 30)
    )

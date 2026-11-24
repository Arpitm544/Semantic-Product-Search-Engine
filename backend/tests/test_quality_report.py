"""Search-quality evaluation: metrics, stage equivalence with serving, and the API."""
import json
import math

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.evaluation import metrics
from src.evaluation.pipeline import (
    STAGES, ExactSemanticSearch, StageRunner, build_engines, build_report, evaluate,
)


# ---------------------------------------------------------------- metrics

def test_ndcg_is_one_for_the_ideal_order_and_lower_otherwise():
    grades = {"a": 3, "b": 2, "c": 0}
    assert metrics.ndcg_at_k(["a", "b", "c"], grades) == pytest.approx(1.0)
    worse = metrics.ndcg_at_k(["c", "b", "a"], grades)
    assert 0 < worse < 1
    expected = (3 / math.log2(3) + 7 / math.log2(4)) / (7 + 3 / math.log2(3))
    assert worse == pytest.approx(expected)


def test_ndcg_counts_unjudged_results_as_irrelevant_and_handles_no_relevant():
    assert metrics.ndcg_at_k(["x", "y"], {"a": 3}) == 0.0
    assert metrics.ndcg_at_k(["a"], {"a": 0}) == 0.0


def test_rank_metrics():
    relevant = {"b", "d"}
    assert metrics.reciprocal_rank(["a", "b"], relevant) == 0.5
    assert metrics.reciprocal_rank(["a"], relevant) == 0.0
    assert metrics.recall_at_k(["b", "x", "d"], relevant, 2) == 0.5
    assert metrics.hit_at_k(["x", "y", "d"], relevant, 2) == 0.0
    assert metrics.hit_at_k(["x", "y", "d"], relevant, 3) == 1.0


def test_percentile_interpolates():
    assert metrics.percentile([], 0.5) == 0.0
    assert metrics.percentile([5], 0.95) == 5.0
    assert metrics.percentile([1, 2, 3, 4], 0.5) == pytest.approx(2.5)
    assert metrics.percentile(list(range(1, 101)), 0.95) == pytest.approx(95.05)


# ---------------------------------------------------------------- pipeline

PRODUCTS = [
    {"id": "p1", "title": "Wireless headphones", "representation_text": "wireless bluetooth headphones over ear"},
    {"id": "p2", "title": "Wired earbuds", "representation_text": "wired earbuds in ear audio"},
    {"id": "p3", "title": "Leather belt", "representation_text": "full grain leather belt brown"},
    {"id": "p4", "title": "Canvas belt", "representation_text": "canvas belt casual"},
    {"id": "p5", "title": "Running shoes", "representation_text": "running shoes lightweight"},
    {"id": "p6", "title": "Noise cancelling headphones", "representation_text": "noise cancelling headphones travel"},
]


class LetterEncoder:
    """Deterministic stand-in for MiniLM: normalized letter counts."""
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


class OverlapReranker:
    """Stand-in cross-encoder: shared-word count."""
    def predict(self, pairs, **_):
        return [len(set(query.lower().split()) & set(text.lower().split())) for query, text in pairs]


@pytest.fixture
def engines():
    encoder = LetterEncoder()
    vectors = encoder.encode([p["representation_text"] for p in PRODUCTS])
    semantic = ExactSemanticSearch(PRODUCTS, encoder, vectors, model_name="letters")
    return build_engines(PRODUCTS, semantic, OverlapReranker())


def test_exact_semantic_search_returns_closest_products_first():
    encoder = LetterEncoder()
    vectors = encoder.encode([p["representation_text"] for p in PRODUCTS])
    results = ExactSemanticSearch(PRODUCTS, encoder, vectors).search("leather belt", 2)
    assert results[0][0]["id"] == "p3"
    assert len(results) == 2
    with pytest.raises(ValueError):
        ExactSemanticSearch(PRODUCTS, encoder, vectors[:2])


@pytest.mark.parametrize("query", ["headphones", "headphnes", "leather belt", "zzzz"])
def test_served_stage_matches_product_search(engines, query):
    """The 'reranked' stage must rank exactly like ProductSearch.search()."""
    engine, keyword_engine = engines
    stages = StageRunner(engine, keyword_engine).run(query)
    served = [item["id"] for item in engine.search(query, limit=10)["results"]]
    assert stages["reranked"][0] == served
    assert set(stages) == {stage_id for stage_id, _, _ in STAGES}
    for ids, milliseconds in stages.values():
        assert len(ids) <= 10 and milliseconds >= 0


def test_report_summarizes_stages_buckets_and_examples(engines):
    engine, keyword_engine = engines
    queries = [
        {"query_id": "q1", "query": "headphones", "kind": "clean", "query_family": "headphones",
         "relevant_doc_ids": ["p1", "p6"], "grades": {"p1": 3, "p6": 3, "p2": 1}},
        {"query_id": "q2", "query": "headphnes", "kind": "deletion", "query_family": "headphones",
         "relevant_doc_ids": ["p1", "p6"], "grades": {"p1": 3, "p6": 3, "p2": 1}},
        {"query_id": "q3", "query": "brown belt", "kind": "clean", "query_family": "brown belt",
         "relevant_doc_ids": ["p3"], "grades": {"p3": 3, "p4": 2}},
    ]
    per_query, latencies = evaluate(engine, keyword_engine, queries)
    report = build_report(per_query, latencies, engine.by_id, {"split": "test"})

    assert report["queryCount"] == 3 and report["split"] == "test"
    assert [stage["id"] for stage in report["stages"]] == [stage_id for stage_id, _, _ in STAGES]
    for stage in report["stages"]:
        assert stage["metrics"]["all"]["queries"] == 3
        assert stage["metrics"]["clean"]["queries"] == 2
        assert stage["metrics"]["typo"]["queries"] == 1
        assert set(stage["byTypoKind"]) == {"deletion"}
        assert 0 <= stage["metrics"]["all"]["ndcg@10"] <= 1
        assert stage["latencyMs"]["p95"] >= stage["latencyMs"]["p50"] >= 0
    families = [example["query"] for example in report["examples"]["wins"]]
    assert len(families) == 2  # one example per query family
    assert all(item["grade"] in {"Exact", "Substitute", "Complement", "Irrelevant", "Unjudged"}
               for example in report["examples"]["wins"] for item in example["rerankedTop"])
    json.dumps(report)  # must be serializable for the API


# ---------------------------------------------------------------- API

def test_quality_endpoint_serves_report_without_sign_in(tmp_path, monkeypatch):
    from api import quality
    from api.main import app

    path = tmp_path / "quality_report.json"
    path.write_text(json.dumps({"version": 1, "stages": [{"id": "keyword"}]}))
    monkeypatch.setattr(quality, "REPORT_PATH", path)
    response = TestClient(app).get("/api/quality")
    assert response.status_code == 200
    assert response.json()["stages"][0]["id"] == "keyword"

    # A rewritten report is picked up without a restart.
    path.write_text(json.dumps({"version": 2, "stages": []}))
    assert TestClient(app).get("/api/quality").json()["version"] == 2


def test_quality_endpoint_reports_missing_or_broken_files(tmp_path, monkeypatch):
    from api import quality
    from api.main import app

    monkeypatch.setattr(quality, "REPORT_PATH", tmp_path / "missing.json")
    response = TestClient(app).get("/api/quality")
    assert response.status_code == 404
    assert "evaluate_quality.py" in response.json()["error"]

    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    monkeypatch.setattr(quality, "REPORT_PATH", broken)
    assert TestClient(app).get("/api/quality").status_code == 503

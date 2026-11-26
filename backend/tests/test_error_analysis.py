"""Error analysis: query types, failure causes and the statistics behind them."""
import json

import numpy as np
import pytest

from scripts import error_analysis as ea
from src.search.query_filters import BrandIndex


@pytest.fixture(scope="module")
def brands():
    products = [{"id": f"n{i}", "brand": "Nike", "title": f"Nike running shoe {i}"} for i in range(6)]
    return BrandIndex(products)


def test_query_types_from_the_correctly_typed_query(brands):
    tags = ea.query_tags("1 1/4 leather belt without buckle", "deletion", brands)
    assert {"length:5-7", "typo:deletion", "negation", "number-or-size"} <= set(tags)
    assert set(ea.query_tags("nike running shoes for men", "clean", brands)) >= {
        "clean", "brand", "accessory-or-for", "audience", "length:5-7"}
    assert ea.query_tags("black dress", "clean", brands) == ["length:1-2", "clean", "color"]


def test_negated_terms_and_numbers():
    assert ea.negated_terms("belt without buckle full grain") == {"buckle", "full"}
    assert ea.negated_terms("non slip yoga mat") == {"slip", "yoga"}
    assert ea.negated_terms("leather belt") == set()
    assert ea.numbers("55 inch tv 4.5 stars") == {"55", "4.5"}
    assert ea.head_word("red running shoes for men") == "shoes"
    assert ea.head_word("womens 7 inch yoga shorts") == "shorts"
    assert ea.head_word("belt without buckle") == "belt"


def record(ranked, relevant):
    return {"ranked": ranked, "relevant": relevant}


def test_failure_causes(brands):
    by_id = {
        "buckle": {"title": "Leather belt with buckle"},
        "plain": {"title": "Leather belt strap no buckle"},
        "tv65": {"title": "65 inch smart TV"},
        "tv55": {"title": "55 inch smart TV"},
        "adidas": {"title": "Adidas running shoes", "brand": "adidas"},
        "nike": {"title": "Nike running shoes", "brand": "Nike"},
        "lamp": {"title": "Desk lamp"},
        "mug": {"title": "Coffee mug"},
    }
    assert ea.failure_cause(record(["lamp"], ["nowhere"]), "coffee mug", by_id, brands) == ("retrieval-miss", None)
    assert ea.failure_cause(record(["buckle", "plain"], ["plain"]), "belt without buckle", by_id, brands) == \
        ("ranking:negation-ignored", 2)
    assert ea.failure_cause(record(["tv65", "tv55"], ["tv55"]), "55 inch tv", by_id, brands) == ("ranking:number-or-size", 2)
    assert ea.failure_cause(record(["adidas", "nike"], ["nike"]), "nike running shoes", by_id, brands) == ("ranking:wrong-brand", 2)
    assert ea.failure_cause(record(["lamp", "mug"], ["mug"]), "coffee mug", by_id, brands) == ("ranking:wrong-product-type", 2)


def test_family_bootstrap_intervals():
    rng = np.random.default_rng(0)
    values = [0.2, 0.2, 0.8, 0.8, 0.5, 0.5]
    families = ["a", "a", "b", "b", "c", "c"]
    mean, (low, high) = ea.bootstrap_mean(values, families, rng, rounds=2000)
    assert mean == pytest.approx(0.5) and low <= 0.5 <= high
    worse = [0.1] * 40
    better = [0.9] * 40
    diff, (low, high) = ea.bootstrap_difference(worse, [f"w{i // 2}" for i in range(40)],
                                                better, [f"b{i // 2}" for i in range(40)], rng, rounds=2000)
    assert diff == pytest.approx(-0.8) and high < 0



def test_cached_rankings_are_rebuilt_when_data_or_model_changes(monkeypatch, tmp_path):
    from unittest.mock import Mock

    encoder, reranker = tmp_path / "encoder", tmp_path / "reranker"
    encoder.mkdir()
    reranker.mkdir()
    weights = reranker / "model.safetensors"
    weights.write_bytes(b"first")
    monkeypatch.setattr(ea, "LTR_CACHE", tmp_path / "ltr")
    monkeypatch.setattr(ea, "OWN_CACHE", tmp_path / "errors" / "validation.json")
    run = Mock(side_effect=[[{"run": 1}], [{"run": 2}], [{"run": 3}], [{"run": 4}]])
    monkeypatch.setattr(ea, "run_pipeline", run)

    products = [{"id": "p1", "title": "Headphones"}]
    rows = [{"query": "headphones", "grades": {"p1": 3}}]
    assert ea.load_rankings(rows, products, encoder, reranker) == [{"run": 1}]
    assert ea.load_rankings(rows, products, encoder, reranker) == [{"run": 1}]
    rows[0]["grades"]["p1"] = 0
    assert ea.load_rankings(rows, products, encoder, reranker) == [{"run": 2}]
    weights.write_bytes(b"second")
    assert ea.load_rankings(rows, products, encoder, reranker) == [{"run": 3}]
    assert ea.load_rankings(rows, products, encoder, reranker, force=True) == [{"run": 4}]
    assert ea.load_rankings(rows, products, encoder, reranker) == [{"run": 4}]
    assert run.call_count == 4



def test_ltr_cache_requires_matching_metadata_and_archive(monkeypatch, tmp_path):
    from unittest.mock import Mock

    encoder, reranker = tmp_path / "encoder", tmp_path / "reranker"
    encoder.mkdir()
    reranker.mkdir()
    products, rows = [{"id": "p1", "title": "Headphones"}], [{"query": "headphones"}]
    identity = ea.ranking_cache_identity(products, rows, encoder, reranker)
    prefix = tmp_path / "ltr"
    monkeypatch.setattr(ea, "LTR_CACHE", prefix)
    monkeypatch.setattr(ea, "OWN_CACHE", tmp_path / "own.json")
    run = Mock(return_value=[{"fresh": True}])
    monkeypatch.setattr(ea, "run_pipeline", run)
    meta = {"rankingIdentity": identity, "queries": [], "features": [
        "keyword_rank", "semantic_rank", "semantic_similarity", "reranker_score"
    ]}
    prefix.with_suffix(".json").write_text(json.dumps(meta))
    archive = prefix.with_suffix(".npz")
    np.savez_compressed(archive, ranking_identity=json.dumps(identity, sort_keys=True), X=[], query=[], ids=[])
    assert ea.load_rankings(rows, products, encoder, reranker) == []
    run.assert_not_called()

    np.savez_compressed(archive, ranking_identity="different run", X=[], query=[], ids=[])
    assert ea.load_rankings(rows, products, encoder, reranker) == [{"fresh": True}]
    run.assert_called_once()

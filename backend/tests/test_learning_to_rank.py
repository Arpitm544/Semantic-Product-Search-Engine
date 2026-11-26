"""Learning to rank: features, the LambdaMART ranker, serving and significance tests."""
import importlib.util
import json
import subprocess
import sys
import textwrap
from unittest.mock import Mock

import numpy as np
import pytest

# LightGBM is never imported here: with PyTorch in the same process it crashes
# on macOS, which is why serving evaluates the exported trees itself.
from src.ranking.features import FEATURE_NAMES, candidate_features
from src.ranking.learned import LearnedRanker, TreeModel
from src.search.product_search import ProductSearch


PRODUCTS = [
    {"id": "a", "title": "Wired earbuds", "brand": "Acme", "representation_text": "wired earbuds audio"},
    {"id": "b", "title": "Wireless headphones", "brand": "Sony", "representation_text": "wireless bluetooth headphones"},
    {"id": "c", "title": "Noise cancelling headphones", "brand": "Bose", "representation_text": "noise cancelling headphones travel"},
]


class Semantic:
    def search(self, query, top_k=10):
        return [(PRODUCTS[2], 0.81), (PRODUCTS[1], 0.64)][:top_k]


def reranker():
    model = Mock()
    model.predict.side_effect = lambda pairs, **_: [
        {"wireless bluetooth headphones": 3.0, "noise cancelling headphones travel": 9.5}.get(text, -2.0)
        for _, text in pairs
    ]
    return model


def features_for(engine, query):
    corrected, _ = engine.spelling.correct(query)
    variations = engine.spelling.alternatives(query)
    ids, sources, signals = engine.find_candidates_detailed(variations, query)
    ranking = engine.rank_candidates_detailed(corrected, ids)
    return candidate_features({"query": query, "corrected": corrected, "variations": variations},
                              ranking, signals, sources, engine.by_id), ranking


def column(matrix, name):
    return matrix[:, FEATURE_NAMES.index(name)]


def test_features_describe_each_candidate_in_blend_order():
    engine = ProductSearch(PRODUCTS, Semantic(), reranker())
    (ids, matrix), ranking = features_for(engine, "sony headphones")
    assert ids == ranking["ids"] and matrix.shape == (len(ids), len(FEATURE_NAMES))
    assert list(column(matrix, "blend_rank")) == list(range(1, len(ids) + 1))
    sony = ids.index("b")
    assert column(matrix, "brand_in_query")[sony] == 1.0
    assert column(matrix, "title_overlap")[sony] == 0.5    # "headphones" is in the title, "sony" only in the brand
    assert column(matrix, "text_overlap")[sony] == 1.0
    assert column(matrix, "reranker_gap").max() == 0.0
    # A product meaning search never found gets a missing similarity, not a fake one.
    if "a" in ids:
        assert np.isnan(column(matrix, "semantic_similarity")[ids.index("a")])


def split(feature, threshold, left, right, default_left=True, missing="None"):
    return {"split_feature": FEATURE_NAMES.index(feature), "threshold": threshold, "decision_type": "<=",
            "default_left": default_left, "missing_type": missing, "internal_value": (_value(left) + _value(right)) / 2,
            "left_child": left, "right_child": right}


def leaf(value):
    return {"leaf_value": value}


def _value(node):
    return node.get("leaf_value", node.get("internal_value"))


def ranker_preferring(tmp_path, feature="title_overlap"):
    """A hand-written two-tree model: a higher `feature` means more relevant."""
    dump = {"feature_names": list(FEATURE_NAMES), "tree_info": [
        {"tree_structure": split(feature, 0.5, leaf(-1.0), leaf(1.0))},
        {"tree_structure": split(feature, 0.8, leaf(-0.2), leaf(0.3))},
    ]}
    path = tmp_path / "model.json"
    path.write_text(json.dumps(dump))
    return LearnedRanker.load(path)


def test_learned_ranker_orders_by_predicted_relevance_and_explains(tmp_path):
    ranker = ranker_preferring(tmp_path)
    X = np.zeros((3, len(FEATURE_NAMES)), dtype="float32")
    X[:, FEATURE_NAMES.index("title_overlap")] = [0.1, 0.9, 0.6]
    ordered, scores = ranker.order(["x", "y", "z"], X)
    assert ordered == ["y", "z", "x"]
    assert scores == {"y": 1.3, "z": 0.8, "x": -1.2}
    factors = ranker.top_factors(X[1])
    assert factors[0]["feature"] == "title_overlap" and factors[0]["effect"] > 0 and factors[0]["label"]


def test_missing_values_follow_lightgbm_rules():
    model = TreeModel({"feature_names": list(FEATURE_NAMES), "tree_info": [
        {"tree_structure": split("semantic_similarity", 0.5, leaf(-1.0), leaf(1.0), default_left=False, missing="NaN")},
    ]})
    row = np.zeros(len(FEATURE_NAMES))
    row[FEATURE_NAMES.index("semantic_similarity")] = np.nan
    assert model.predict_row(row) == 1.0          # NaN takes the default (right) branch
    row[FEATURE_NAMES.index("semantic_similarity")] = 0.2
    assert model.predict_row(row) == -1.0


def test_a_model_with_other_features_is_refused(tmp_path):
    path = tmp_path / "other.json"
    path.write_text(json.dumps({"feature_names": ["a", "b"], "tree_info": []}))
    with pytest.raises(ValueError):
        LearnedRanker.load(path)


@pytest.mark.skipif(importlib.util.find_spec("lightgbm") is None, reason="LightGBM is only needed for training")
def test_served_scores_match_lightgbm_exactly():
    """Train a real model in a separate process and compare its predictions with ours."""
    script = textwrap.dedent(f"""
        import json, numpy as np, lightgbm
        rng = np.random.default_rng(0)
        X = rng.random((600, {len(FEATURE_NAMES)}))
        X[rng.random(X.shape) < 0.1] = np.nan          # missing values, like unmatched products
        y = (np.nan_to_num(X[:, 3]) * 3.99).astype(int)
        m = lightgbm.LGBMRanker(objective="lambdarank", n_estimators=60, num_leaves=15, min_child_samples=5, verbose=-1)
        m.fit(X, y, group=[30] * 20, feature_name={list(FEATURE_NAMES)!r})
        print(json.dumps({{"dump": m.booster_.dump_model(), "X": np.where(np.isnan(X), None, X).tolist(),
                          "pred": m.booster_.predict(X).tolist()}}))
    """)
    output = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True).stdout
    data = json.loads(output)
    X = np.array([[np.nan if v is None else v for v in row] for row in data["X"]])
    assert np.abs(TreeModel(data["dump"]).predict(X) - np.array(data["pred"])).max() < 1e-9


def test_search_uses_the_learned_order_and_says_so(tmp_path):
    engine = ProductSearch(PRODUCTS, Semantic(), reranker())
    blend = engine.search("headphones", fuzzy=False)
    assert all(item["explanation"]["ranker"] == "blend" for item in blend["results"])

    engine.learned_ranker = ranker_preferring(tmp_path, "semantic_similarity")
    learned = engine.search("headphones", fuzzy=False)
    assert learned["searchMode"].endswith("-learned")
    first = learned["results"][0]["explanation"]
    assert first["ranker"] == "learned" and first["learnedFactors"][0]["feature"] == "semantic_similarity"
    assert {item["id"] for item in learned["results"]} == {item["id"] for item in blend["results"]}


def test_a_failing_model_falls_back_to_the_blend():
    engine = ProductSearch(PRODUCTS, Semantic(), reranker())
    engine.learned_ranker = Mock()
    engine.learned_ranker.order.side_effect = RuntimeError("broken model")
    results = engine.search("headphones", fuzzy=False)["results"]
    assert results and all(item["explanation"]["ranker"] == "blend" for item in results)


def test_the_ranker_setting_and_missing_model(monkeypatch, tmp_path):
    from api import search_service

    monkeypatch.setenv("SEARCH_RANKER", "LEARNED")
    assert search_service.ranker_choice() == "learned"
    monkeypatch.setenv("SEARCH_RANKER", "something-else")
    assert search_service.ranker_choice() == "blend"
    assert search_service.load_learned_ranker("blend") is None
    monkeypatch.setattr("src.ranking.learned.MODEL_PATH", tmp_path / "missing.txt")
    assert search_service.load_learned_ranker("learned") is None   # search still starts


def test_significance_tests_behave():
    from scripts.train_ltr import bootstrap_interval, randomization_p_value

    rng = np.random.default_rng(1)
    same = np.zeros(200)
    assert randomization_p_value(same, rng, rounds=2000) == 1.0
    better = rng.normal(0.05, 0.05, size=200)
    assert randomization_p_value(better, rng, rounds=2000) < 0.01
    low, high = bootstrap_interval(better, rng, rounds=2000)
    assert low < better.mean() < high and low > 0



def test_incomplete_ranker_artifact_falls_back_to_the_blend(monkeypatch, tmp_path):
    import json
    from api import search_service
    from src.ranking import learned

    model_path = tmp_path / "model.json"
    model_path.write_text(json.dumps({"feature_names": list(FEATURE_NAMES)}))
    monkeypatch.setattr(learned, "MODEL_PATH", model_path)
    assert search_service.load_learned_ranker("learned") is None

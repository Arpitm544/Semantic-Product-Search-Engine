"""Serve the LambdaMART ranking model trained by scripts/train_ltr.py.

The model is LightGBM's own JSON dump (trees with split rules and leaf
values), evaluated here with plain Python/NumPy. Serving therefore needs no
LightGBM: on macOS, LightGBM's OpenMP library and PyTorch's crash when both
load into one process, and the search server always loads PyTorch.
train_ltr.py checks that these scores equal LightGBM's own predictions.
"""
import json
import math
from pathlib import Path

import numpy as np

from src.ranking.features import FEATURE_LABELS, FEATURE_NAMES

MODEL_PATH = Path(__file__).resolve().parents[2] / "ranking" / "ltr_model.json"


def _goes_left(node, value):
    """LightGBM's rule for one numeric split, including missing values."""
    missing = node.get("missing_type", "None")
    if math.isnan(value):
        if missing == "NaN":
            return node["default_left"]
        value = 0.0
    if missing == "Zero" and abs(value) <= 1e-35:
        return node["default_left"]
    return value <= node["threshold"]


def _value(node):
    return node["leaf_value"] if "leaf_value" in node else node["internal_value"]


class TreeModel:
    """A sum of regression trees from LightGBM's dump_model() output."""

    def __init__(self, dump):
        if tuple(dump.get("feature_names", ())) != FEATURE_NAMES:
            raise ValueError("The ranking model was trained with different features.")
        self.trees = [info["tree_structure"] for info in dump["tree_info"]]

    def predict_row(self, row):
        total = 0.0
        for node in self.trees:
            while "leaf_value" not in node:
                node = node["left_child"] if _goes_left(node, float(row[node["split_feature"]])) else node["right_child"]
            total += node["leaf_value"]
        return total

    def predict(self, matrix):
        return np.array([self.predict_row(row) for row in np.asarray(matrix, dtype="float64")])

    def contributions(self, row):
        """How much each feature moved this score (path attribution, as in Saabas):
        each split adds the change in the tree's expected value to its feature."""
        effects = np.zeros(len(FEATURE_NAMES))
        for node in self.trees:
            while "leaf_value" not in node:
                child = node["left_child"] if _goes_left(node, float(row[node["split_feature"]])) else node["right_child"]
                effects[node["split_feature"]] += _value(child) - _value(node)
                node = child
        return effects


class LearnedRanker:
    """Orders candidates by the learned model and names the factors behind each score."""

    def __init__(self, model):
        self.model = model

    @classmethod
    def load(cls, path=None):
        path = Path(path or MODEL_PATH)
        if not path.is_file():
            raise OSError(f"No ranking model at {path}")
        return cls(TreeModel(json.loads(path.read_text())))

    def scores(self, matrix):
        return self.model.predict(matrix)

    def order(self, ids, matrix):
        """Highest predicted relevance first; ties keep the current order."""
        scores = self.scores(matrix)
        positions = sorted(range(len(ids)), key=lambda index: (-scores[index], index))
        return [ids[index] for index in positions], {ids[index]: float(scores[index]) for index in positions}

    def top_factors(self, row, count=3):
        """The features that moved this product's score most."""
        effects = self.model.contributions(row)
        top = sorted(range(len(FEATURE_NAMES)), key=lambda index: -abs(effects[index]))[:count]
        return [{"feature": FEATURE_NAMES[index], "label": FEATURE_LABELS[FEATURE_NAMES[index]],
                 "effect": round(float(effects[index]), 3)} for index in top if effects[index] != 0]

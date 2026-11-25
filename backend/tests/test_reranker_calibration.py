"""Check the learned probability contract used by search."""

from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from src.search.product_search import ProductSearch
from src.search.relevance import CalibratedReranker, PlattScaling
from src.semantic.prepare_esci import write_jsonl
from src.semantic.train_reranker import fit_platt, load_splits


def test_platt_scaling_uses_exact_substitute_and_complement_as_positive():
    rows = [{"grade": value} for value in [0, 0, 0, 1, 2, 3, 0, 2]]
    logits = np.asarray([-8, -7, -6, -1, 0, 1, 0.5, 2])
    calibration = fit_platt(logits, rows)
    assert 0 <= calibration.probability(-1000) < calibration.probability(-3)
    assert calibration.probability(-3) < calibration.probability(-1) < calibration.probability(1000) <= 1


def test_catalog_passes_training_format_and_exposes_probability():
    model = Mock()
    model.predict.return_value = [0.0]
    reranker = CalibratedReranker(model, PlattScaling(1, 0))
    engine = ProductSearch([{"id": "1", "title": "Earbuds", "description": "Wireless",
                             "representation_text": "[Brand] Sample | [Title] Earbuds"}], None, reranker)
    result, = engine.search("earbuds", fuzzy=False)["results"]
    assert model.predict.call_args.args == ([("earbuds", "[Title] Earbuds | [Description] Wireless")],)
    assert result["relevanceProbability"] == 0.5


def test_calibration_split_cannot_reuse_a_training_query_family(tmp_path: Path):
    for name, family in [("train", "train"), ("calibration", "train"), ("test", "test")]:
        write_jsonl(tmp_path / f"{name}.jsonl", [{"family": family, "grade": grade} for grade in range(4)])
    with pytest.raises(ValueError, match="disjoint query families"):
        load_splits(tmp_path)

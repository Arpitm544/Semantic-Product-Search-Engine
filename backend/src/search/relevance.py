"""Calibrated ESCI relevance for the shopping cross-encoder."""

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path

from src.config import PROJECT_ROOT

RELEVANCE_THRESHOLD = 0.20
BASE_RERANKER_PATH = "models/ms-marco-MiniLM-L6-v2"
ESCI_RERANKER_PATH = "models/colab-export/esci-reranker"
CALIBRATION_FILE = "calibration.json"
MAX_LENGTH = 256


def configured_reranker_path():
    default = (ESCI_RERANKER_PATH if (PROJECT_ROOT / ESCI_RERANKER_PATH / CALIBRATION_FILE).is_file()
               else BASE_RERANKER_PATH)
    return os.environ.get("RERANKER_MODEL_PATH") or default


def product_pair_text(product):
    title = (product.get("title") or "")[:512]
    description = (product.get("description") or "")[:2000]
    return f"[Title] {title}" + (f" | [Description] {description}" if description else "")


def weights_sha256(directory):
    digest = hashlib.sha256()
    with (Path(directory) / "model.safetensors").open("rb") as weights:
        for block in iter(lambda: weights.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class PlattScaling:
    slope: float
    intercept: float

    def __post_init__(self):
        if not math.isfinite(self.slope) or self.slope <= 0 or not math.isfinite(self.intercept):
            raise ValueError("Invalid Platt calibration coefficients.")

    def probability(self, logit):
        log_odds = self.slope * float(logit) + self.intercept
        return 1 / (1 + math.exp(-log_odds)) if log_odds >= 0 else (
            math.exp(log_odds) / (1 + math.exp(log_odds))
        )


class CalibratedReranker:
    def __init__(self, model, calibration):
        self.model = model
        self.calibration = calibration

    def predict(self, pairs, **kwargs):
        return self.model.predict(pairs, **kwargs)


def load_reranker(path, device="cpu"):
    from sentence_transformers import CrossEncoder
    from torch.nn import Identity

    directory = Path(path)
    sidecar = directory / CALIBRATION_FILE
    calibration = None
    if sidecar.is_file():
        metadata = json.loads(sidecar.read_text())
        if (metadata["method"] != "platt" or metadata["version"] != 1
                or metadata["max_length"] != MAX_LENGTH or metadata["relevant_labels"] != ["E", "S", "C"]
                or metadata["weights_sha256"] != weights_sha256(directory)):
            raise ValueError("Calibration does not match the reranker artifact.")
        calibration = PlattScaling(metadata["slope"], metadata["intercept"])
    model = CrossEncoder(str(directory), local_files_only=True, device=device, max_length=MAX_LENGTH,
                         activation_fn=Identity() if calibration is not None else None)
    return CalibratedReranker(model, calibration) if calibration is not None else model


def relevance_probability(reranker, score):
    if isinstance(reranker, CalibratedReranker) and math.isfinite(score):
        return reranker.calibration.probability(score)
    return None

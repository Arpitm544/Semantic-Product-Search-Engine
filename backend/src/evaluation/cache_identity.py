"""Identify the inputs to the offline baseline ranking pipeline."""

from hashlib import sha256
import json

from src.semantic.dataset import catalog_fingerprint
from src.semantic.identity import model_digest


def ranking_cache_identity(products, rows, encoder_path, reranker_path):
    # Update the version when the baseline ranking or its model configuration changes.
    return {
        "pipelineVersion": 1,
        "catalogSha256": catalog_fingerprint(products),
        "catalogOrderSha256": sha256(json.dumps([product["id"] for product in products]).encode()).hexdigest(),
        "queriesSha256": sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
        "encoderSha256": model_digest(encoder_path),
        "rerankerSha256": model_digest(reranker_path),
    }

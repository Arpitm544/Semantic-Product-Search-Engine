"""Shared reciprocal-rank fusion and tunable pipeline parameters."""

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Optional

from src.config import PROJECT_ROOT

# Final order: 25% retrieval rank, 75% cross-encoder rank, fused as 1 / (60 + rank).
RRF_K = 60
RETRIEVAL_WEIGHT = 0.25
RERANKER_WEIGHT = 0.75
DEFAULT_TUNED_PARAMS_PATH = "reports/tuning/best_params_balanced.json"


@dataclass(frozen=True)
class PipelineParams:
    """Hyperparameters controlling retrieval depth, spelling weights, RRF, and blending."""

    bm25_k: int = 50
    semantic_k: int = 50
    hybrid_rrf_k: int = 60
    keyword_weight: float = 1.0
    fuzzy_weight: float = 0.85
    semantic_weight: float = 1.0
    semantic_corrected_weight: float = 0.5
    variation_limit: int = 50
    variation_rrf_k: int = 60
    original_variation_weight: float = 1.0
    corrected_variation_weight: float = 1.0
    alt_variation_weight: float = 1.0
    rerank_k: Optional[int] = None
    blend_rrf_k: int = RRF_K
    retrieval_weight: float = RETRIEVAL_WEIGHT
    reranker_weight: float = RERANKER_WEIGHT

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        allowed = set(cls.__dataclass_fields__)
        filtered = {key: value for key, value in data.items() if key in allowed}
        return cls(**filtered)

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text()))


def configured_pipeline_params():
    """Load tuned pipeline parameters when available, or fall back to baseline defaults."""
    override = os.environ.get("PIPELINE_PARAMS_PATH")
    target = (PROJECT_ROOT / override).resolve() if override else (PROJECT_ROOT / DEFAULT_TUNED_PARAMS_PATH)
    if target.is_file():
        return PipelineParams.load(target)
    return PipelineParams()


def blend_ranks(
    retrieval_positions,
    reranker_positions,
    rrf_k=RRF_K,
    retrieval_weight=RETRIEVAL_WEIGHT,
    reranker_weight=RERANKER_WEIGHT,
):
    return {
        key: retrieval_weight / (rrf_k + rank) + reranker_weight / (rrf_k + reranker_positions[key])
        for key, rank in retrieval_positions.items()
    }

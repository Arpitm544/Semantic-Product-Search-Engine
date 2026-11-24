"""Shared reciprocal-rank fusion for catalog and Shopping candidates."""

# Final order: 25% retrieval rank, 75% cross-encoder rank, fused as 1 / (60 + rank).
RRF_K = 60
RETRIEVAL_WEIGHT = 0.25
RERANKER_WEIGHT = 0.75


def blend_ranks(retrieval_positions, reranker_positions):
    return {key: RETRIEVAL_WEIGHT / (RRF_K + rank) + RERANKER_WEIGHT / (RRF_K + reranker_positions[key])
            for key, rank in retrieval_positions.items()}

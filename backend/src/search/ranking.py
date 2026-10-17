"""Shared reciprocal-rank fusion for catalog and Shopping candidates."""


def blend_ranks(retrieval_positions, reranker_positions):
    return {key: 0.25 / (60 + rank) + 0.75 / (60 + reranker_positions[key])
            for key, rank in retrieval_positions.items()}

"""Dataset-independent ranking metrics."""

import math
from typing import Any, List, Set


def precision_at_k(retrieved_ids: List[Any], relevant_ids: Set[Any], k: int) -> float:
    """Calculate Precision@K."""
    if k <= 0:
        return 0.0
    top_k = retrieved_ids[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
    return hits / float(k)


def recall_at_k(retrieved_ids: List[Any], relevant_ids: Set[Any], k: int) -> float:
    """Calculate Recall@K."""
    if not relevant_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
    return hits / float(len(relevant_ids))


def dcg_at_k(retrieved_ids: List[Any], relevant_ids: Set[Any], k: int) -> float:
    """Calculate Discounted Cumulative Gain at K."""
    score = 0.0
    for idx, doc_id in enumerate(retrieved_ids[:k]):
        if doc_id in relevant_ids:
            score += 1.0 / math.log2(idx + 2)  # idx+2 since rank starts at 1
    return score


def ndcg_at_k(retrieved_ids: List[Any], relevant_ids: Set[Any], k: int) -> float:
    """Calculate Normalized Discounted Cumulative Gain at K."""
    actual_dcg = dcg_at_k(retrieved_ids, relevant_ids, k)
    ideal_retrieved = list(relevant_ids)
    ideal_dcg = dcg_at_k(ideal_retrieved, relevant_ids, k)
    if ideal_dcg == 0.0:
        return 0.0
    return actual_dcg / ideal_dcg


def reciprocal_rank(retrieved_ids: List[Any], relevant_ids: Set[Any]) -> float:
    """Calculate Reciprocal Rank (1/rank of first relevant item)."""
    for idx, doc_id in enumerate(retrieved_ids):
        if doc_id in relevant_ids:
            return 1.0 / float(idx + 1)
    return 0.0


def average_precision(retrieved_ids: List[Any], relevant_ids: Set[Any]) -> float:
    """Calculate Average Precision (AP)."""
    if not relevant_ids:
        return 0.0
    hits = 0
    sum_precisions = 0.0
    for idx, doc_id in enumerate(retrieved_ids):
        if doc_id in relevant_ids:
            hits += 1
            sum_precisions += hits / (idx + 1.0)
    return sum_precisions / len(relevant_ids)

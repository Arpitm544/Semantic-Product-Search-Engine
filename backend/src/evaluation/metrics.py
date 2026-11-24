"""Ranking metrics for graded relevance judgments.

Amazon ESCI labels each judged product Exact (3), Substitute (2), Complement (1)
or Irrelevant (0). Products a system returns that were never judged count as
irrelevant, which is the standard convention for offline ranking evaluation.
"""

import math


def dcg(gains):
    """Discounted cumulative gain: later positions count for less."""
    return sum((2 ** gain - 1) / math.log2(position + 1)
               for position, gain in enumerate(gains, start=1))


def ndcg_at_k(retrieved_ids, grades, k=10):
    """Compare the returned order with the best possible order of judged products."""
    ideal = dcg(sorted((grade for grade in grades.values() if grade > 0), reverse=True)[:k])
    if ideal == 0:
        return 0.0
    return dcg([grades.get(product_id, 0) for product_id in retrieved_ids[:k]]) / ideal


def reciprocal_rank(retrieved_ids, relevant_ids, k=10):
    """One over the position of the first relevant product within the top k."""
    for position, product_id in enumerate(retrieved_ids[:k], start=1):
        if product_id in relevant_ids:
            return 1 / position
    return 0.0


def recall_at_k(retrieved_ids, relevant_ids, k):
    """Share of the relevant products that appear in the top k."""
    if not relevant_ids:
        return 0.0
    return len(set(retrieved_ids[:k]) & relevant_ids) / len(relevant_ids)


def hit_at_k(retrieved_ids, relevant_ids, k):
    """Whether at least one relevant product appears in the top k."""
    return float(bool(set(retrieved_ids[:k]) & relevant_ids))


METRIC_NAMES = ("ndcg@10", "mrr@10", "recall@10", "hit@5")


def query_metrics(retrieved_ids, grades, relevant_ids):
    """Score one ranked list against one query's judgments."""
    relevant = set(relevant_ids)
    return {
        "ndcg@10": ndcg_at_k(retrieved_ids, grades, 10),
        "mrr@10": reciprocal_rank(retrieved_ids, relevant, 10),
        "recall@10": recall_at_k(retrieved_ids, relevant, 10),
        "hit@5": hit_at_k(retrieved_ids, relevant, 5),
    }


def mean_metrics(rows):
    """Average each metric over a group of per-query results."""
    if not rows:
        return {"queries": 0, **{name: 0.0 for name in METRIC_NAMES}}
    return {"queries": len(rows), **{
        name: sum(row[name] for row in rows) / len(rows) for name in METRIC_NAMES
    }}


def percentile(values, fraction):
    """Linear-interpolated percentile of a list of numbers (fraction in 0..1)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower))

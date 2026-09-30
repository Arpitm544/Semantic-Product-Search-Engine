"""
Information Retrieval (IR) Evaluation Harness for Keyword Baseline.
Addresses TR-009 / BR-004: Standard IR metrics against held-out evaluation set.
"""
import json
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Set
import numpy as np

from src.config import (
    EVAL_SET_PATH,
    BASELINE_METRICS_PATH,
    BM25_INDEX_PATH,
    PROCESSED_DATA_PATH,
)
from src.baseline.bm25 import BM25Okapi
from src.data.load_data import load_cleaned_products


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


def evaluate_baseline(
    eval_set_path: Path = EVAL_SET_PATH,
    output_path: Path = BASELINE_METRICS_PATH,
    top_ks: List[int] = [5, 10],
) -> Dict[str, Any]:
    """Run full evaluation on held-out evaluation query set."""
    if not eval_set_path.exists():
        raise FileNotFoundError(f"Evaluation set not found at {eval_set_path}")

    with open(eval_set_path, "r", encoding="utf-8") as f:
        eval_queries = json.load(f)

    # Ensure BM25 index is available
    if BM25_INDEX_PATH.exists():
        bm25 = BM25Okapi.load(BM25_INDEX_PATH)
    else:
        products = load_cleaned_products()
        bm25 = BM25Okapi().fit(products)
        bm25.save(BM25_INDEX_PATH)

    results_by_k = {k: {"p": [], "r": [], "ndcg": []} for k in top_ks}
    mrr_list = []
    latencies_ms = []

    for item in eval_queries:
        query = item["query"]
        relevant_ids = set(item["relevant_doc_ids"])

        t0 = time.perf_counter()
        search_results = bm25.search(query, top_k=max(top_ks))
        latency = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(latency)

        retrieved_ids = [prod["id"] for prod, _ in search_results]

        for k in top_ks:
            p = precision_at_k(retrieved_ids, relevant_ids, k)
            r = recall_at_k(retrieved_ids, relevant_ids, k)
            ndcg = ndcg_at_k(retrieved_ids, relevant_ids, k)

            results_by_k[k]["p"].append(p)
            results_by_k[k]["r"].append(r)
            results_by_k[k]["ndcg"].append(ndcg)

        rr = reciprocal_rank(retrieved_ids, relevant_ids)
        mrr_list.append(rr)

    metrics_summary = {
        "model": "BM25Okapi (Keyword Baseline)",
        "total_queries": len(eval_queries),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "latency_ms": {
            "mean": float(np.mean(latencies_ms)),
            "p50": float(np.percentile(latencies_ms, 50)),
            "p95": float(np.percentile(latencies_ms, 95)),
        },
        "mrr": float(np.mean(mrr_list)),
        "metrics": {},
    }

    for k in top_ks:
        metrics_summary["metrics"][f"k={k}"] = {
            f"precision@{k}": float(np.mean(results_by_k[k]["p"])),
            f"recall@{k}": float(np.mean(results_by_k[k]["r"])),
            f"ndcg@{k}": float(np.mean(results_by_k[k]["ndcg"])),
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metrics_summary, f, indent=2)

    print(f"Baseline evaluation saved to {output_path}")
    return metrics_summary


def main():
    metrics = evaluate_baseline()
    print("\n--- BM25 Keyword Baseline Benchmark Results ---")
    print(f"Queries Evaluated: {metrics['total_queries']}")
    print(f"MRR: {metrics['mrr']:.4f}")
    print(f"Latency (p50 / p95): {metrics['latency_ms']['p50']:.2f}ms / {metrics['latency_ms']['p95']:.2f}ms")
    for k_key, vals in metrics["metrics"].items():
        print(f"{k_key}:")
        for m, v in vals.items():
            print(f"  {m}: {v:.4f}")


if __name__ == "__main__":
    main()

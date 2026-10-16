"""
Evaluation Harness for Semantic Vector Search (Sentence-BERT + FAISS).
Measures standard IR metrics (MRR, Precision@K, Recall@K, NDCG@K, Latency).
"""
import json
import time
from pathlib import Path
from typing import Any, Dict, List
import numpy as np

from src.config import (
    EVAL_SET_PATH,
    SEMANTIC_METRICS_PATH,
    FAISS_INDEX_PATH,
    FAISS_ID_MAP_PATH,
)
from src.semantic.vector_search import SemanticVectorSearch
from src.data.load_data import load_cleaned_products
from src.baseline.evaluate_baseline import (
    precision_at_k,
    recall_at_k,
    ndcg_at_k,
    reciprocal_rank,
    average_precision,
)


def evaluate_semantic(
    eval_set_path: Path = EVAL_SET_PATH,
    output_path: Path = SEMANTIC_METRICS_PATH,
    top_ks: List[int] = [5, 10],
) -> Dict[str, Any]:
    """Runs evaluation benchmark for Semantic Vector Search."""
    if not eval_set_path.exists():
        raise FileNotFoundError(f"Evaluation set not found at {eval_set_path}")

    with open(eval_set_path, "r", encoding="utf-8") as f:
        eval_queries = json.load(f)

    # Ensure FAISS index is available
    if FAISS_INDEX_PATH.exists() and FAISS_ID_MAP_PATH.exists():
        semantic_engine = SemanticVectorSearch.load(FAISS_INDEX_PATH, FAISS_ID_MAP_PATH)
    else:
        products = load_cleaned_products()
        semantic_engine = SemanticVectorSearch()
        semantic_engine.fit(products)
        semantic_engine.save(FAISS_INDEX_PATH, FAISS_ID_MAP_PATH)

    results_by_k = {k: {"p": [], "r": [], "ndcg": []} for k in top_ks}
    mrr_list = []
    ap_list = []
    latencies_ms = []

    for item in eval_queries:
        query = item["query"]
        relevant_ids = set(item["relevant_doc_ids"])

        t0 = time.perf_counter()
        search_results = semantic_engine.search(query, top_k=max(top_ks))
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
        ap = average_precision(retrieved_ids, relevant_ids)
        ap_list.append(ap)

    metrics_summary = {
        "model": "Sentence-BERT + FAISS (Semantic Search)",
        "total_queries": len(eval_queries),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "latency_ms": {
            "mean": float(np.mean(latencies_ms)),
            "p50": float(np.percentile(latencies_ms, 50)),
            "p95": float(np.percentile(latencies_ms, 95)),
        },
        "mrr": float(np.mean(mrr_list)),
        "map": float(np.mean(ap_list)),
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

    print(f"Semantic evaluation saved to {output_path}")
    return metrics_summary


def main():
    metrics = evaluate_semantic()
    print("\n--- Semantic Vector Search Benchmark Results ---")
    print(f"Queries Evaluated: {metrics['total_queries']}")
    print(f"MRR: {metrics['mrr']:.4f}")
    print(f"MAP: {metrics['map']:.4f}")
    print(f"Latency (p50 / p95): {metrics['latency_ms']['p50']:.2f}ms / {metrics['latency_ms']['p95']:.2f}ms")
    for k_key, vals in metrics["metrics"].items():
        print(f"{k_key}:")
        for m, v in vals.items():
            print(f"  {m}: {v:.4f}")


if __name__ == "__main__":
    main()

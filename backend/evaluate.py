import json
import os
import time
import math
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from app.bm25 import BM25Okapi

def dcg_at_k(r, k):
    r = np.asarray(r, dtype=float)[:k]
    if not r.size:
        return 0.0
    return float(np.sum(r / np.log2(np.arange(2, r.size + 2))))

def ndcg_at_k(r, k):
    dcg_max = dcg_at_k(sorted(r, reverse=True), k)
    if not dcg_max:
        return 0.0
    return dcg_at_k(r, k) / dcg_max

def evaluate_search_engine():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    eval_set_path = os.path.join(base_dir, "..", "data", "eval_set.json")
    index_file = os.path.join(base_dir, "index_store", "faiss_index.bin")
    meta_file = os.path.join(base_dir, "index_store", "products_meta.json")
    bm25_file = os.path.join(base_dir, "index_store", "bm25_index.pkl")
    results_output = os.path.join(base_dir, "..", "data", "eval_results.json")

    with open(eval_set_path, "r", encoding="utf-8") as f:
        eval_queries = json.load(f)

    with open(meta_file, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    faiss_index = faiss.read_index(index_file)
    bm25_index = BM25Okapi.load(bm25_file)
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    modes = ["keyword", "semantic", "hybrid"]
    metrics_summary = {}
    k_eval = 5

    for mode in modes:
        precisions = []
        recalls = []
        ndcgs = []
        reciprocal_ranks = []
        latencies = []

        for q_item in eval_queries:
            query = q_item["query"]
            relevant_ids = set(q_item["relevant_doc_ids"])

            t0 = time.time()
            retrieved_ids = []

            if mode == "keyword":
                ranked = bm25_index.search(query, top_k=k_eval)
                retrieved_ids = [metadata[idx]["id"] for idx, _ in ranked]

            elif mode == "semantic":
                q_vec = model.encode([query], convert_to_numpy=True).astype(np.float32)
                faiss.normalize_L2(q_vec)
                scores, indices = faiss_index.search(q_vec, k_eval)
                for idx in indices[0]:
                    if idx >= 0 and idx < len(metadata):
                        retrieved_ids.append(metadata[idx]["id"])

            elif mode == "hybrid":
                # RRF Fusion
                q_vec = model.encode([query], convert_to_numpy=True).astype(np.float32)
                faiss.normalize_L2(q_vec)
                f_scores, f_indices = faiss_index.search(q_vec, len(metadata))

                sem_ranks = {f_indices[0][r]: r + 1 for r in range(len(f_indices[0])) if f_indices[0][r] >= 0}
                bm25_ranked = bm25_index.search(query, top_k=len(metadata))
                bm25_ranks = {doc_idx: rank + 1 for rank, (doc_idx, _) in enumerate(bm25_ranked)}

                all_doc_indices = set(sem_ranks.keys()).union(set(bm25_ranks.keys()))
                rrf_scores = []
                for doc_idx in all_doc_indices:
                    r_sem = sem_ranks.get(doc_idx, 1000)
                    r_bm25 = bm25_ranks.get(doc_idx, 1000)
                    rrf = (1.0 / (60.0 + r_sem)) + (1.0 / (60.0 + r_bm25))
                    rrf_scores.append((doc_idx, rrf))

                rrf_scores.sort(key=lambda x: x[1], reverse=True)
                retrieved_ids = [metadata[doc_idx]["id"] for doc_idx, _ in rrf_scores[:k_eval]]

            latency_ms = (time.time() - t0) * 1000.0
            latencies.append(latency_ms)

            # Binary relevance vector
            relevance = [1 if doc_id in relevant_ids else 0 for doc_id in retrieved_ids]

            # Precision@K
            p_k = sum(relevance) / k_eval
            precisions.append(p_k)

            # Recall@K
            r_k = sum(relevance) / len(relevant_ids) if relevant_ids else 0.0
            recalls.append(r_k)

            # NDCG@K
            ndcg_k = ndcg_at_k(relevance, k_eval)
            ndcgs.append(ndcg_k)

            # MRR
            rr = 0.0
            for rank_idx, rel in enumerate(relevance, start=1):
                if rel == 1:
                    rr = 1.0 / rank_idx
                    break
            reciprocal_ranks.append(rr)

        metrics_summary[mode] = {
            "precision_at_5": round(float(np.mean(precisions)), 4),
            "recall_at_5": round(float(np.mean(recalls)), 4),
            "ndcg_at_5": round(float(np.mean(ndcgs)), 4),
            "mrr": round(float(np.mean(reciprocal_ranks)), 4),
            "p50_latency_ms": round(float(np.percentile(latencies, 50)), 2),
            "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2),
        }

    output_payload = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "totalQueries": len(eval_queries),
        "k": k_eval,
        "metrics": metrics_summary
    }

    with open(results_output, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)

    print("=== Offline Evaluation Benchmark Complete ===")
    print(json.dumps(output_payload, indent=2))
    return output_payload

if __name__ == "__main__":
    evaluate_search_engine()

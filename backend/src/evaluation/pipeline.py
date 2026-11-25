"""Measure each stage of the serving search pipeline on held-out ESCI queries.

The stages reuse the production classes (ProductSearch, HybridSearch, BM25 and
the spelling corrector), so the numbers describe the code that answers real
requests. The only substitution is semantic retrieval: production asks the
Atlas vector index, while evaluation runs an exact in-memory search over the
same embeddings so it needs no database or network.

Evaluated stages and baselines:
  keyword   BM25 over the catalog text
  spelling  BM25 over the query and its spelling-corrected variations
  semantic  fine-tuned MiniLM embeddings only
  hybrid    keyword + semantic + spelling, fused by reciprocal rank
  reranked  hybrid candidates reordered by the cross-encoder (what users see)
"""

from collections import defaultdict
from datetime import datetime, timezone
import time

from src.evaluation.inference import infer
from src.evaluation.metrics import mean_metrics, percentile, query_metrics
from src.keyword_search.bm25 import search_bm25
from src.search.product_search import ProductSearch

TOP_K = 10
GRADE_LABELS = {3: "Exact", 2: "Substitute", 1: "Complement", 0: "Irrelevant"}

STAGES = (
    ("keyword", "Keyword (BM25)",
     "Classic word matching over product titles and descriptions."),
    ("spelling", "+ Spelling correction",
     "Also searches catalog-aware corrections such as “headphnes” → “headphones”."),
    ("semantic", "Semantic only",
     "Fine-tuned MiniLM embeddings match by meaning instead of exact words."),
    ("hybrid", "Hybrid retrieval",
     "Keyword, spelling and semantic lists fused with reciprocal-rank fusion."),
    ("reranked", "Hybrid + reranker",
     "A cross-encoder rescores hybrid candidates. This is what the site serves."),
)


class ExactSemanticSearch:
    """Exact cosine search over precomputed product embeddings.

    Matches the interface ProductSearch expects from AtlasVectorSearch:
    search(query, top_k) -> [(product, score), ...].
    """

    def __init__(self, products, encoder, product_vectors, model_name=None):
        import numpy as np

        self.products = products
        self.encoder = encoder
        self.vectors = np.asarray(product_vectors, dtype="float32")
        if self.vectors.shape[0] != len(products):
            raise ValueError("Each product needs exactly one embedding.")
        self.model_name = model_name

    def encode_query(self, query):
        return self.encoder.encode([query], normalize_embeddings=True,
                                   show_progress_bar=False)[0]

    def search(self, query, top_k=10):
        import numpy as np

        limit = min(top_k, len(self.products))
        if limit <= 0:
            return []
        scores = self.vectors @ np.asarray(self.encode_query(query), dtype="float32")
        top = np.argpartition(-scores, limit - 1)[:limit]
        # Stable tie-break on catalog position keeps runs reproducible.
        top = sorted(top.tolist(), key=lambda index: (-float(scores[index]), index))
        return [(self.products[index], float(scores[index])) for index in top]


def encode_products(encoder, products, batch_size=64):
    """Embed products with the same text Atlas setup uses."""
    import numpy as np

    texts = [product.get("representation_text") or product.get("title", "") for product in products]
    vectors = encoder.encode(texts, batch_size=batch_size, normalize_embeddings=True,
                             show_progress_bar=True, convert_to_numpy=True)
    return np.asarray(vectors, dtype="float32")


class StageRunner:
    """Run every stage for one query and time each one."""

    def __init__(self, engine, keyword_engine):
        self.engine = engine
        # Same ProductSearch code without embeddings: keyword + spelling variations.
        self.keyword_engine = keyword_engine

    @staticmethod
    def timed(function):
        start = time.perf_counter()
        value = function()
        return value, (time.perf_counter() - start) * 1000

    def run(self, query):
        """Return {stage_id: (ranked_ids, milliseconds)} for one query."""
        engine = self.engine
        query = query.strip()
        results = {}

        results["keyword"] = self.timed(lambda: [
            product["id"] for product, _ in search_bm25(engine.hybrid.lexical, query, TOP_K)
        ])

        def spelling():
            variations = self.keyword_engine.spelling.alternatives(query)
            return self.keyword_engine.find_candidates(variations, query)[0][:TOP_K]
        results["spelling"] = self.timed(spelling)

        results["semantic"] = self.timed(lambda: [
            product["id"] for product, _ in engine.semantic.search(query, TOP_K)
        ])

        # Hybrid and reranked follow ProductSearch.search() step by step, so
        # the reranker reuses the hybrid candidates instead of searching twice.
        def hybrid():
            corrected, _ = engine.spelling.correct(query)
            variations = engine.spelling.alternatives(query)
            candidates, _ = engine.find_candidates(variations, query)
            return corrected, candidates
        (corrected, candidates), hybrid_ms = self.timed(hybrid)
        results["hybrid"] = (candidates[:TOP_K], hybrid_ms)

        if candidates:
            (ranked, _), rerank_ms = self.timed(
                lambda: engine.rank_candidates(corrected, candidates))
        else:
            ranked, rerank_ms = [], 0.0
        results["reranked"] = (ranked[:TOP_K], hybrid_ms + rerank_ms)
        return results


def bucket_for(row):
    return "clean" if row["kind"] == "clean" else "typo"


def summarize(per_query, latencies):
    """Group per-query scores into overall, clean/typo and typo-kind averages."""
    stages = []
    for stage_id, label, description in STAGES:
        groups = defaultdict(list)
        for row in per_query:
            scores = row["stages"][stage_id]
            groups["all"].append(scores)
            groups[row["bucket"]].append(scores)
            if row["kind"] != "clean":
                groups[f"kind:{row['kind']}"].append(scores)
        times = latencies[stage_id]
        stages.append({
            "id": stage_id,
            "label": label,
            "description": description,
            "metrics": {name: mean_metrics(groups[name]) for name in ("all", "clean", "typo")},
            "byTypoKind": {
                name.split(":", 1)[1]: mean_metrics(values)
                for name, values in sorted(groups.items()) if name.startswith("kind:")
            },
            "latencyMs": {
                "p50": percentile(times, 0.50),
                "p95": percentile(times, 0.95),
                "mean": sum(times) / len(times) if times else 0.0,
            },
        })
    return stages


def describe_results(ids, by_id, grades, count=3):
    return [{
        "title": by_id[product_id].get("title", ""),
        "grade": GRADE_LABELS.get(grades.get(product_id), "Unjudged"),
    } for product_id in ids[:count] if product_id in by_id]


def pick_examples(per_query, by_id, count=4):
    """Biggest improvements from keyword to the served ranking, one per query family."""
    def unique_families(rows):
        seen, chosen = set(), []
        for row in rows:
            if row["family"] in seen:
                continue
            seen.add(row["family"])
            chosen.append(row)
            if len(chosen) == count:
                break
        return chosen

    def delta(row):
        return row["stages"]["reranked"]["ndcg@10"] - row["stages"]["keyword"]["ndcg@10"]

    wins = unique_families(sorted(per_query, key=lambda row: (-delta(row), row["queryId"])))
    misses = unique_families(sorted(
        (row for row in per_query if row["stages"]["reranked"]["ndcg@10"] < 0.2),
        key=lambda row: (row["stages"]["reranked"]["ndcg@10"], row["queryId"]),
    ))

    def present(row):
        return {
            "query": row["query"],
            "kind": row["kind"],
            "keywordNdcg": row["stages"]["keyword"]["ndcg@10"],
            "rerankedNdcg": row["stages"]["reranked"]["ndcg@10"],
            "keywordTop": describe_results(row["ids"]["keyword"], by_id, row["grades"]),
            "rerankedTop": describe_results(row["ids"]["reranked"], by_id, row["grades"]),
        }
    return {"wins": [present(row) for row in wins], "misses": [present(row) for row in misses]}


def evaluate(engine, keyword_engine, queries, progress=None):
    """Score every stage on every query and return per-query rows and latencies."""
    runner = StageRunner(engine, keyword_engine)
    per_query = []
    latencies = defaultdict(list)
    for index, row in enumerate(queries, start=1):
        results = runner.run(row["query"])
        grades = row.get("grades") or {pid: 1 for pid in row["relevant_doc_ids"]}
        scored = {}
        for stage_id, (ids, milliseconds) in results.items():
            scored[stage_id] = query_metrics(ids, grades, row["relevant_doc_ids"])
            latencies[stage_id].append(milliseconds)
        per_query.append({
            "queryId": row["query_id"],
            "query": row["query"],
            "kind": row["kind"],
            "bucket": bucket_for(row),
            "family": row.get("query_family", row["query_id"]),
            "grades": grades,
            "ids": {stage_id: ids for stage_id, (ids, _) in results.items()},
            "stages": scored,
        })
        if progress:
            progress(index, len(queries))
    return per_query, latencies


def build_report(per_query, latencies, by_id, metadata):
    """Assemble the JSON document served by /api/quality."""
    stages = summarize(per_query, latencies)
    return {
        "version": 2,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **metadata,
        "queryCount": len(per_query),
        "stages": stages,
        "statistics": infer(per_query, latencies, stages),
        "examples": pick_examples(per_query, by_id),
    }


def build_engines(products, semantic, reranker, params=None):
    """The served pipeline, plus the same pipeline without embeddings."""
    engine = ProductSearch(products, semantic, reranker, params=params)
    keyword_engine = ProductSearch(products, None, reranker, params=params)
    return engine, keyword_engine

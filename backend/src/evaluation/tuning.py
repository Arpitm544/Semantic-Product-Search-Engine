"""Precomputation and exact replay helpers for Optuna pipeline tuning."""

from collections import Counter, defaultdict
import re

from src.evaluation.metrics import mean_metrics, query_metrics
from src.keyword_search.bm25 import fit_bm25, search_bm25
from src.search.product_search import brand_title
from src.search.ranking import PipelineParams, blend_ranks
from src.search.relevance import CalibratedReranker, product_pair_text
from src.search.typos import FrequencySpelling

TOP_K = 10


def build_lexical_and_spelling(products):
    """Match ProductSearch.prepare_keyword_search vocabulary and BM25 index."""
    word_counts = Counter()
    for product in products:
        text = brand_title(product)
        word_counts.update(set(re.findall(r"\b[a-z]+\b", text.lower())))
    lexical = fit_bm25(products)
    lexical["products"] = products
    spelling = FrequencySpelling(word_counts)
    return lexical, spelling


def variation_weight(variation, original_query, corrected_query, params):
    if variation == original_query:
        return params.original_variation_weight
    if corrected_query and variation == corrected_query:
        return params.corrected_variation_weight
    return params.alt_variation_weight


class LazyScoreStore:
    """Cache cross-encoder scores per (corrected_query, product_id) with on-demand fill."""

    def __init__(self, by_id, reranker, initial_scores=None):
        self.by_id = by_id
        self.reranker = reranker
        self.scores = initial_scores if initial_scores is not None else {}
        self.on_demand_predictions = 0

    def _pair_text(self, product):
        if isinstance(self.reranker, CalibratedReranker):
            return product_pair_text(product)
        return product.get("representation_text") or product.get("title", "")

    def ensure_scores(self, corrected_query, product_ids):
        query_cache = self.scores.setdefault(corrected_query, {})
        missing = [pid for pid in product_ids if pid not in query_cache]
        if not missing:
            return
        pairs = [(corrected_query, self._pair_text(self.by_id[pid])) for pid in missing]
        predicted = self.reranker.predict(pairs, batch_size=32, show_progress_bar=False)
        for pid, score in zip(missing, predicted):
            query_cache[pid] = float(score)
        self.on_demand_predictions += len(missing)

    def get_scores(self, corrected_query, product_ids):
        self.ensure_scores(corrected_query, product_ids)
        query_cache = self.scores[corrected_query]
        return [query_cache[pid] for pid in product_ids]


def precompute_validation_data(
    products,
    semantic,
    reranker,
    queries,
    max_stage_k=80,
    max_rerank_precompute=100,
    progress=None,
):
    """Precompute BM25/semantic top-K lists and initial reranker scores for queries."""
    by_id = {product["id"]: product for product in products}
    lexical, spelling = build_lexical_and_spelling(products)

    bm25_lists = {}
    semantic_lists = {}
    cached_queries = []
    rerank_pool_by_corrected = defaultdict(list)
    seen_pairs = defaultdict(set)

    total = len(queries)
    for index, row in enumerate(queries, start=1):
        query = row["query"].strip()
        corrected_query, _ = spelling.correct(query)
        corrected_diff = corrected_query if corrected_query != query else None
        variations = spelling.alternatives(query)

        # Rank union candidates by unweighted RRF so top max_rerank_precompute covers typical trials.
        pool_scores = defaultdict(float)
        for variation in variations:
            if variation not in bm25_lists:
                bm25_lists[variation] = [
                    product["id"] for product, _ in search_bm25(lexical, variation, max_stage_k)
                ]
                semantic_lists[variation] = (
                    [product["id"] for product, _ in semantic.search(variation, max_stage_k)]
                    if semantic is not None else []
                )
            for rank, pid in enumerate(bm25_lists[variation], start=1):
                pool_scores[pid] += 1.0 / (30 + rank)
            for rank, pid in enumerate(semantic_lists[variation], start=1):
                pool_scores[pid] += 1.0 / (30 + rank)

        top_pool = sorted(pool_scores, key=lambda pid: (-pool_scores[pid], pid))[:max_rerank_precompute]
        for pid in top_pool:
            if pid not in seen_pairs[corrected_query]:
                seen_pairs[corrected_query].add(pid)
                rerank_pool_by_corrected[corrected_query].append(pid)

        grades = row.get("grades") or {pid: 1 for pid in row["relevant_doc_ids"]}
        cached_queries.append({
            "query_id": row["query_id"],
            "query": query,
            "corrected_query": corrected_query,
            "corrected_diff": corrected_diff,
            "variations": variations,
            "grades": grades,
            "relevant_doc_ids": row["relevant_doc_ids"],
            "kind": row["kind"],
        })
        if progress and (index == total or index % 100 == 0):
            progress("retrieval", index, total)

    score_store = LazyScoreStore(by_id, reranker)
    corrected_items = list(rerank_pool_by_corrected.items())
    for index, (corrected_query, pids) in enumerate(corrected_items, start=1):
        score_store.ensure_scores(corrected_query, pids)
        if progress and (index == len(corrected_items) or index % 100 == 0):
            progress("reranker", index, len(corrected_items))

    return {
        "queries": cached_queries,
        "bm25_lists": bm25_lists,
        "semantic_lists": semantic_lists,
        "reranker_scores": score_store.scores,
    }


def _hybrid_for_variation(bm25_ids, semantic_ids, params):
    scores = defaultdict(float)
    bm25_k = max(params.bm25_k, params.variation_limit)
    for rank, pid in enumerate(bm25_ids[:bm25_k], start=1):
        scores[pid] += params.keyword_weight / (params.hybrid_rrf_k + rank)

    if semantic_ids:
        semantic_k = max(params.semantic_k, params.variation_limit)
        for rank, pid in enumerate(semantic_ids[:semantic_k], start=1):
            scores[pid] += params.semantic_weight / (params.hybrid_rrf_k + rank)

    ranked_ids = sorted(scores, key=lambda pid: (-scores[pid], str(pid)))
    return ranked_ids[:params.variation_limit]


def replay_query(entry, bm25_lists, semantic_lists, score_store, params: PipelineParams):
    """Replay ProductSearch candidate generation and reranking identically to live serving."""
    scores = defaultdict(float)
    original_query = entry["query"]
    corrected_diff = entry["corrected_diff"]

    for variation in entry["variations"]:
        weight = variation_weight(variation, original_query, corrected_diff, params)
        if weight <= 0:
            continue
        hybrid_ids = _hybrid_for_variation(
            bm25_lists[variation], semantic_lists[variation], params,
        )
        for position, pid in enumerate(hybrid_ids, start=1):
            scores[pid] += weight / (params.variation_rrf_k + position)

    candidate_ids = sorted(scores, key=lambda pid: (-scores[pid], pid))
    if not candidate_ids:
        return [], [], 0

    hybrid_top = candidate_ids[:TOP_K]
    if params.rerank_k is not None:
        candidate_ids = candidate_ids[:params.rerank_k]

    retrieval_positions = {pid: pos for pos, pid in enumerate(candidate_ids, start=1)}
    model_scores = score_store.get_scores(entry["corrected_query"], candidate_ids)
    reranked_indexes = sorted(
        range(len(candidate_ids)),
        key=lambda idx: (-float(model_scores[idx]), idx),
    )
    reranker_positions = {
        candidate_ids[idx]: pos for pos, idx in enumerate(reranked_indexes, start=1)
    }
    combined_scores = blend_ranks(
        retrieval_positions,
        reranker_positions,
        rrf_k=params.blend_rrf_k,
        retrieval_weight=params.retrieval_weight,
        reranker_weight=params.reranker_weight,
    )
    ranked_ids = sorted(
        candidate_ids,
        key=lambda pid: (-combined_scores[pid], retrieval_positions[pid]),
    )
    return hybrid_top, ranked_ids[:TOP_K], len(candidate_ids)


def evaluate_cached(cache_data, score_store, params: PipelineParams, latency_model=None):
    """Evaluate PipelineParams across all cached validation queries."""
    per_query_reranked = []
    per_query_hybrid = []
    rerank_counts = []
    bm25_lists = cache_data["bm25_lists"]
    semantic_lists = cache_data["semantic_lists"]

    for entry in cache_data["queries"]:
        hybrid_top, reranked_top, cand_count = replay_query(
            entry, bm25_lists, semantic_lists, score_store, params,
        )
        per_query_hybrid.append(query_metrics(hybrid_top, entry["grades"], entry["relevant_doc_ids"]))
        per_query_reranked.append(query_metrics(reranked_top, entry["grades"], entry["relevant_doc_ids"]))
        rerank_counts.append(cand_count)

    hybrid_summary = mean_metrics(per_query_hybrid)
    reranked_summary = mean_metrics(per_query_reranked)
    mean_candidates = sum(rerank_counts) / len(rerank_counts) if rerank_counts else 0.0
    if latency_model is not None:
        est_ms = (
            latency_model["hybrid_mean_ms"]
            + latency_model["rerank_intercept_ms"]
            + latency_model["rerank_per_candidate_ms"] * mean_candidates
        )
    else:
        est_ms = mean_candidates

    return {
        "hybrid": hybrid_summary,
        "reranked": reranked_summary,
        "mean_rerank_candidates": mean_candidates,
        "estimated_search_ms": est_ms,
    }

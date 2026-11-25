"""Manage a search: prepare the query, find matches, then rank the products.

Spelling rules are in typos.py. Keyword and semantic retrieval are in hybrid.py.
Read ProductSearch.search() first to follow the full process.
"""

from collections import Counter, defaultdict
import re
import logging
from threading import Lock

from src.keyword_search.bm25 import fit_bm25
from src.search.hybrid import HybridSearch
from src.search.typos import FrequencySpelling
from src.search.ranking import PipelineParams, blend_ranks
from src.search.explanations import RankSignals, explanation
from src.search.relevance import CalibratedReranker, product_pair_text, relevance_probability
from src.ranking.features import candidate_features


logger = logging.getLogger(__name__)


def brand_title(product):
    """Use the brand and title as the product's keyword-search text."""
    match = re.search(r"\[Brand\]\s*([^|]+)", product.get("representation_text", ""))
    brand = match.group(1).strip() if match else product.get("brand", "")
    return f"{brand} {product.get('title', '')}"


class ProductSearch:
    """Keep the prepared search tools together so requests can reuse them."""

    def __init__(self, products, semantic, reranker, model_lock=None, params=None):
        self.products = products
        self.by_id = {product["id"]: product for product in products}
        self.semantic = semantic
        self.reranker = reranker
        self.lock = model_lock if model_lock is not None else Lock()
        self.params = params if params is not None else PipelineParams()
        # Optional LambdaMART model (src/ranking/learned.py); None keeps the configured blend.
        self.learned_ranker = None
        self.prepare_keyword_search(products, semantic)

    def prepare_keyword_search(self, products, semantic):
        """Build keyword matching and spelling vocabulary from brands and titles."""
        word_counts = Counter()
        keyword_products = []
        for product in products:
            text = brand_title(product)
            words = set(re.findall(r"\b[a-z]+\b", text.lower()))
            word_counts.update(words)
            keyword_products.append(product)

        keyword_index = fit_bm25(keyword_products)
        keyword_index["products"] = products
        self.hybrid = HybridSearch(products, semantic, lexical=keyword_index, params=self.params)
        self.spelling = FrequencySpelling(word_counts)
        self.hybrid.spelling = self.spelling

    def search(self, query, limit=20, fuzzy=True):
        """Prepare the query, retrieve candidates, rank them, and return results."""
        # 1. Correct spelling and choose the query variations to search.
        query = query.strip()
        corrected_query = query
        corrections = []
        query_variations = [query]
        if fuzzy:
            corrected_query, corrections = self.spelling.correct(query)
            query_variations = self.spelling.alternatives(query)

        response = {
            "query": query,
            "correctedQuery": corrected_query if corrections else None,
            "corrections": corrections,
            "queryAlternatives": query_variations,
            "searchMode": ("expanded-hybrid-reranked" if self.semantic is not None
                           else "expanded-keyword-reranked"),
            "semanticModel": getattr(self.semantic, "model_name", None),
            "candidateCount": 0,
            "results": [],
        }
        if not query or limit <= 0:
            return response

        # 2. Find possible matches with keyword and semantic search.
        # Only one request uses the shared models at a time, but network-backed
        # semantic search (Atlas) locks just its encoding so other requests are
        # not blocked while it waits on the database.
        if getattr(self.semantic, "manages_model_lock", False) is True:
            candidate_ids, match_sources, signals = self.find_candidates_detailed(query_variations, query)
        else:
            with self.lock:
                candidate_ids, match_sources, signals = self.find_candidates_detailed(query_variations, query)
        if not candidate_ids:
            return response

        # 3. Put the best matches first, then build the response.
        ranking = self.rank_candidates_detailed(corrected_query, candidate_ids)
        ranked_ids, scores = ranking["ids"], ranking["scores"]
        context = {"query": query, "corrected": corrected_query, "variations": query_variations}
        learned = self.learned_order(context, ranking, signals, match_sources)
        if learned is not None:
            ranked_ids, scores, rows = learned
        response["searchMode"] += "-learned" if learned is not None else ""
        response["candidateCount"] = len(ranked_ids)
        weights = {"retrieval": self.params.retrieval_weight, "reranker": self.params.reranker_weight}
        for product_id in ranked_ids[:limit]:
            product = self.by_id[product_id]
            details = explanation(corrected_query, product, RankSignals(
                retrieval_rank=ranking["retrieval"][product_id],
                reranker_rank=ranking["reranker"][product_id],
                reranker_score=ranking["model_scores"][product_id],
                blended_score=scores[product_id], candidate_count=len(ranked_ids),
                spelling_match="fuzzy" in match_sources[product_id], **signals[product_id]),
                weights=weights)
            details["ranker"] = "learned" if learned is not None else "blend"
            if learned is not None:
                details["learnedFactors"] = self.learned_ranker.top_factors(rows[product_id])
            response["results"].append({
                **product,
                "score": scores[product_id],
                "relevanceProbability": relevance_probability(self.reranker, ranking["model_scores"][product_id]),
                "matchSources": sorted(match_sources[product_id]) + ["reranker"],
                "explanation": details,
            })
        return response

    def learned_order(self, context, ranking, signals, match_sources):
        """Reorder candidates with the learned ranker, or None to keep the blend.

        Any model failure falls back to the blend so search keeps working."""
        if self.learned_ranker is None:
            return None
        try:
            ids, matrix = candidate_features(context, ranking, signals, match_sources, self.by_id)
            ordered, scores = self.learned_ranker.order(ids, matrix)
        except Exception:
            logger.exception("Learned ranker failed; using the blend")
            return None
        return ordered, scores, {product_id: matrix[index] for index, product_id in enumerate(ids)}

    def find_candidates(self, query_variations, original_query):
        """Give points to products found across the query variations."""
        candidate_ids, match_sources, _ = self.find_candidates_detailed(query_variations, original_query)
        return candidate_ids, match_sources

    def _variation_weight(self, variation, original_query, corrected_query):
        if variation == original_query:
            return self.params.original_variation_weight
        if corrected_query and variation == corrected_query:
            return self.params.corrected_variation_weight
        return self.params.alt_variation_weight

    def find_candidates_detailed(self, query_variations, original_query):
        """find_candidates(), plus each product's best keyword and semantic rank."""
        scores = defaultdict(float)
        match_sources = defaultdict(set)
        signals = defaultdict(lambda: {"keyword_rank": None, "semantic_rank": None, "semantic_similarity": None})
        corrected_query = None
        if len(query_variations) > 1:
            corrected, _ = self.spelling.correct(original_query)
            if corrected != original_query:
                corrected_query = corrected
        for query in query_variations:
            weight = self._variation_weight(query, original_query, corrected_query)
            if weight <= 0:
                continue
            matches = self.hybrid.search(query, self.params.variation_limit, fuzzy=False)
            for position, product in enumerate(matches["results"], start=1):
                product_id = product["id"]
                # Earlier matches earn more points. Repeated matches add up.
                scores[product_id] += weight / (self.params.variation_rrf_k + position)
                match_sources[product_id].update(product["matchSources"])
                if query != original_query:
                    match_sources[product_id].add("fuzzy")
                remember_signals(signals[product_id], product)

        candidate_ids = sorted(scores, key=lambda product_id: (-scores[product_id], product_id))
        return candidate_ids, match_sources, signals

    def rank_candidates(self, query, candidate_ids):
        """Combine retrieval order (25%) with reranker order (75%)."""
        ranking = self.rank_candidates_detailed(query, candidate_ids)
        return ranking["ids"], ranking["scores"]

    def rank_candidates_detailed(self, query, candidate_ids):
        """rank_candidates(), plus each product's retrieval rank, reranker rank and score."""
        if self.params.rerank_k is not None:
            candidate_ids = candidate_ids[:self.params.rerank_k]
        retrieval_positions = {
            product_id: position
            for position, product_id in enumerate(candidate_ids, start=1)
        }

        # Ask the model how well the query matches each product's text.
        query_product_pairs = []
        for product_id in candidate_ids:
            product = self.by_id[product_id]
            text = (product_pair_text(product) if isinstance(self.reranker, CalibratedReranker)
                    else product.get("representation_text") or product.get("title", ""))
            query_product_pairs.append((query, text))
        with self.lock:
            model_scores = self.reranker.predict(
                query_product_pairs, batch_size=32, show_progress_bar=False,
            )

        # On a tied model score, keep the original retrieval order.
        reranked_indexes = sorted(
            range(len(candidate_ids)),
            key=lambda index: (-float(model_scores[index]), index),
        )
        reranker_positions = {}
        for position, index in enumerate(reranked_indexes, start=1):
            reranker_positions[candidate_ids[index]] = position

        combined_scores = blend_ranks(
            retrieval_positions,
            reranker_positions,
            rrf_k=self.params.blend_rrf_k,
            retrieval_weight=self.params.retrieval_weight,
            reranker_weight=self.params.reranker_weight,
        )

        ranked_ids = sorted(
            candidate_ids,
            key=lambda product_id: (
                -combined_scores[product_id], retrieval_positions[product_id],
            ),
        )
        return {
            "ids": ranked_ids, "scores": combined_scores,
            "retrieval": retrieval_positions, "reranker": reranker_positions,
            "model_scores": {product_id: float(model_scores[index]) for index, product_id in enumerate(candidate_ids)},
        }


def best_rank(current, new):
    return new if current is None or (new is not None and new < current) else current


def remember_signals(signals, product):
    """Keep the best keyword rank, semantic rank and similarity seen for a product."""
    ranks = product.get("sourceRanks", {})
    signals["keyword_rank"] = best_rank(signals["keyword_rank"], min(
        (rank for source, rank in ranks.items() if source in ("keyword", "fuzzy")), default=None))
    signals["semantic_rank"] = best_rank(signals["semantic_rank"], min(
        (rank for source, rank in ranks.items() if source.startswith("semantic")), default=None))
    if product.get("semanticScore") is not None:
        signals["semantic_similarity"] = max(signals["semantic_similarity"] or -1.0, product["semanticScore"])

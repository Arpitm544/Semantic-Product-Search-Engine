"""Manage a search: prepare the query, find matches, then rank the products.

Spelling rules are in typos.py. Keyword and semantic retrieval are in hybrid.py.
Read ProductSearch.search() first to follow the full process.
"""

from collections import Counter, defaultdict
import re
from threading import Lock

from src.keyword_search.bm25 import fit_bm25
from src.search.hybrid import HybridSearch
from src.search.typos import FrequencySpelling


def brand_title(product):
    """Use the brand and title as the product's keyword-search text."""
    match = re.search(r"\[Brand\]\s*([^|]+)", product.get("representation_text", ""))
    brand = match.group(1).strip() if match else product.get("brand", "")
    return f"{brand} {product.get('title', '')}"


class ProductSearch:
    """Keep the prepared search tools together so requests can reuse them."""

    def __init__(self, products, semantic, reranker, model_lock=None):
        self.products = products
        self.by_id = {product["id"]: product for product in products}
        self.semantic = semantic
        self.reranker = reranker
        self.lock = model_lock if model_lock is not None else Lock()
        self.prepare_keyword_search(products, semantic)

    def prepare_keyword_search(self, products, semantic):
        """Build keyword matching and spelling vocabulary from brands and titles."""
        word_counts = Counter()
        keyword_products = []
        for product in products:
            text = brand_title(product)
            words = set(re.findall(r"\b[a-z]+\b", text.lower()))
            word_counts.update(words)
            keyword_products.append({**product, "representation_text": text})

        keyword_index = fit_bm25(keyword_products)
        keyword_index["products"] = products
        self.hybrid = HybridSearch(products, semantic, lexical=keyword_index)
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
            "searchMode": "expanded-hybrid-reranked",
            "semanticModel": "fine-tuned",
            "total": 0,
            "results": [],
        }
        if not query or limit <= 0:
            return response

        # Only one request uses the shared search models at a time.
        with self.lock:
            # 2. Find possible matches with keyword and semantic search.
            candidate_ids, match_sources = self.find_candidates(query_variations, fuzzy)
            if not candidate_ids:
                return response

            # 3. Put the best matches first, then build the response.
            ranked_ids, scores = self.rank_candidates(corrected_query, candidate_ids)
            response["total"] = len(ranked_ids)
            for product_id in ranked_ids[:limit]:
                product = self.by_id[product_id]
                response["results"].append({
                    **product,
                    "score": scores[product_id],
                    "matchSources": sorted(match_sources[product_id]) + ["reranker"],
                })
        return response

    def find_candidates(self, query_variations, fuzzy):
        """Give points to products found across the query variations."""
        scores = defaultdict(float)
        match_sources = defaultdict(set)
        for query in query_variations:
            matches = self.hybrid.search(query, 50, fuzzy=fuzzy)
            for position, product in enumerate(matches["results"], start=1):
                product_id = product["id"]
                # Earlier matches earn more points. Repeated matches add up.
                scores[product_id] += 1 / (60 + position)
                match_sources[product_id].update(product["matchSources"])

        candidate_ids = sorted(scores, key=lambda product_id: (-scores[product_id], product_id))
        return candidate_ids, match_sources

    def rank_candidates(self, query, candidate_ids):
        """Combine retrieval order (25%) with reranker order (75%)."""
        retrieval_positions = {
            product_id: position
            for position, product_id in enumerate(candidate_ids, start=1)
        }

        # Ask the model how well the query matches each product's text.
        query_product_pairs = []
        for product_id in candidate_ids:
            product = self.by_id[product_id]
            text = product.get("representation_text") or product.get("title", "")
            query_product_pairs.append((query, text))
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

        combined_scores = {}
        for product_id in candidate_ids:
            retrieval_score = 0.25 / (60 + retrieval_positions[product_id])
            reranker_score = 0.75 / (60 + reranker_positions[product_id])
            combined_scores[product_id] = retrieval_score + reranker_score

        ranked_ids = sorted(
            candidate_ids,
            key=lambda product_id: (
                -combined_scores[product_id], retrieval_positions[product_id],
            ),
        )
        return ranked_ids, combined_scores

"""Combine keyword matches, spelling corrections, and meaning-based matches."""

from collections import defaultdict

from src.keyword_search.bm25 import fit_bm25, search_bm25, tokenize
from src.search.typos import CatalogSpelling


class HybridSearch:
    """Combine word matching with meaning-based matching in one search."""

    def __init__(self, products, semantic=None, semantic_model=None, lexical=None):
        if len({product["id"] for product in products}) != len(products):
            raise ValueError("Catalog product IDs must be unique.")
        self.products = products
        self.lexical = lexical if lexical is not None else fit_bm25(products)
        self.spelling = CatalogSpelling(self.lexical["idf"])
        self.semantic = semantic
        self.semantic_model = semantic_model

    def search(self, query, limit=20, fuzzy=True):
        """Prepare the query, collect ranked matches, and combine them."""
        query = query.strip()
        # 1. Correct the query when spelling correction is enabled.
        corrected_query = query
        corrections = []
        if fuzzy:
            corrected_query, corrections = self.spelling.correct(query)
        mode = "hybrid" if self.semantic is not None else "bm25-fuzzy"
        payload = {
            "query": query,
            "correctedQuery": corrected_query if corrections else None,
            "corrections": corrections,
            "searchMode": mode,
            "semanticModel": self.semantic_model,
            "total": 0,
            "results": [],
        }
        if not tokenize(query) or limit <= 0:
            return payload

        # 2. Run keyword search and, when available, semantic search.
        rankings = self.collect_rankings(query, corrected_query, corrections, limit)

        # 3. Merge the lists into one score and result list per product.
        ranked_ids, results = self.combine_rankings(rankings, limit)
        payload["total"] = len(ranked_ids)
        payload["results"] = results
        return payload

    def collect_rankings(self, query, corrected_query, corrections, limit):
        """Keep the results of each search method with its scoring weight."""
        rankings = [("keyword", 1.0, search_bm25(self.lexical, query, len(self.products)))]
        if corrections:
            rankings.append((
                "fuzzy", 0.85, search_bm25(self.lexical, corrected_query, len(self.products)),
            ))
        if self.semantic is not None:
            candidate_k = min(len(self.products), max(50, limit))
            rankings.append(("semantic", 1.0, self.semantic.search(query, candidate_k)))
            if corrections:
                rankings.append((
                    "semantic-corrected", 0.5, self.semantic.search(corrected_query, candidate_k),
                ))

        return rankings

    def combine_rankings(self, rankings, limit):
        """Reward early matches and products found by multiple methods."""
        # Higher-ranked matches earn more points; repeated matches add up.
        scores = defaultdict(float)
        sources = defaultdict(list)
        products_by_id = {}
        for source, weight, ranked in rankings:
            for rank, (product, _) in enumerate(ranked, start=1):
                product_id = product["id"]
                products_by_id[product_id] = product
                scores[product_id] += weight / (60 + rank)
                sources[product_id].append(source)

        # Sort by combined score and attach the matching methods to each result.
        ranked_ids = sorted(scores, key=lambda product_id: (-scores[product_id], str(product_id)))
        results = [
            {**products_by_id[product_id], "score": scores[product_id],
             "matchSources": sources[product_id]}
            for product_id in ranked_ids[:limit]
        ]
        return ranked_ids, results


"""Fuse ranked lists without mixing BM25 and cosine score scales."""

from collections import defaultdict

from src.baseline.bm25 import fit_bm25, search_bm25, tokenize
from src.search.typos import CatalogSpelling


class HybridSearch:
    def __init__(self, products, semantic=None, semantic_model=None, lexical=None):
        if len({product["id"] for product in products}) != len(products):
            raise ValueError("Catalog product IDs must be unique.")
        self.products = products
        self.lexical = lexical if lexical is not None else fit_bm25(products)
        self.spelling = CatalogSpelling(self.lexical["idf"])
        self.semantic = semantic
        self.semantic_model = semantic_model

    def search(self, query, limit=20, fuzzy=True):
        query = query.strip()
        corrected, corrections = self.spelling.correct(query) if fuzzy else (query, [])
        mode = "hybrid" if self.semantic is not None else "bm25-fuzzy"
        payload = {
            "query": query, "correctedQuery": corrected if corrections else None,
            "corrections": corrections, "searchMode": mode,
            "semanticModel": self.semantic_model, "total": 0, "results": [],
        }
        if not tokenize(query) or limit <= 0:
            return payload

        rankings = [("keyword", 1.0, search_bm25(self.lexical, query, len(self.products)))]
        if corrections:
            rankings.append((
                "fuzzy", 0.85, search_bm25(self.lexical, corrected, len(self.products)),
            ))
        if self.semantic is not None:
            candidate_k = min(len(self.products), max(50, limit))
            rankings.append(("semantic", 1.0, self.semantic.search(query, candidate_k)))
            if corrections:
                rankings.append((
                    "semantic-corrected", 0.5, self.semantic.search(corrected, candidate_k),
                ))

        scores = defaultdict(float)
        sources = defaultdict(list)
        products_by_id = {}
        for source, weight, ranked in rankings:
            for rank, (product, _) in enumerate(ranked, start=1):
                product_id = product["id"]
                products_by_id[product_id] = product
                scores[product_id] += weight / (60 + rank)
                sources[product_id].append(source)

        ids = sorted(scores, key=lambda product_id: (-scores[product_id], str(product_id)))
        payload["total"] = len(ids)
        payload["results"] = [
            {**products_by_id[product_id], "score": scores[product_id],
             "matchSources": sources[product_id]}
            for product_id in ids[:limit]
        ]
        return payload


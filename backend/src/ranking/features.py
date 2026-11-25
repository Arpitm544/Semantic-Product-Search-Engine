"""Features for learning to rank, built from signals the search already computes.

One row per candidate product. Training (scripts/train_ltr.py) and serving
(ProductSearch.search) call the same function, so the model always sees
features computed exactly the same way.
"""
import math
import re

import numpy as np

from src.keyword_search.bm25 import tokenize
from src.search.typos import STOP_WORDS

MISSING_RANK = 200.0   # a method that did not find the product at all

# Name and plain-language meaning of every feature, in matrix column order.
FEATURES = (
    ("blend_rank", "Position under the current 25/75 blend"),
    ("retrieval_rank", "Position after keyword + meaning retrieval"),
    ("reranker_rank", "Position by the careful check (cross-encoder)"),
    ("reranker_score", "Careful-check score"),
    ("reranker_gap", "Careful-check score minus the best in this search"),
    ("reranker_z", "Careful-check score compared with the other candidates"),
    ("keyword_rank", "Keyword (BM25) rank"),
    ("has_keyword", "Found by keyword search"),
    ("semantic_rank", "Meaning-search rank"),
    ("has_semantic", "Found by meaning search"),
    ("semantic_similarity", "Meaning similarity (cosine)"),
    ("similarity_gap", "Similarity minus the best in this search"),
    ("spelling_match", "Matched a spelling correction"),
    ("query_corrected", "The search had a typo"),
    ("query_variations", "Spelling variations searched"),
    ("query_words", "Words in the search"),
    ("title_overlap", "Share of search words in the title"),
    ("text_overlap", "Share of search words anywhere in the product text"),
    ("brand_in_query", "Product brand named in the search"),
    ("title_words", "Words in the title"),
    ("candidate_count", "Candidates for this search"),
)
FEATURE_NAMES = tuple(name for name, _ in FEATURES)
FEATURE_LABELS = dict(FEATURES)


def query_terms(query):
    return [word for word in dict.fromkeys(tokenize(query)) if word not in STOP_WORDS and len(word) > 1]


def _share(terms, words):
    return sum(term in words for term in terms) / len(terms) if terms else 0.0


def _brand_words(product):
    return [word for word in re.findall(r"[a-z0-9]+", str(product.get("brand") or "").lower()) if len(word) > 1]


def _rank(value):
    return MISSING_RANK if value is None else float(value)


def candidate_features(context, ranking, signals, match_sources, by_id):
    """Feature matrix for one search, rows in the current blend order.

    context: {"query", "corrected", "variations"}
    ranking: ProductSearch.rank_candidates_detailed() output
    signals: per-product keyword/semantic ranks from find_candidates_detailed()
    """
    ids = ranking["ids"]
    terms = query_terms(context["corrected"])
    query_words = set(tokenize(context["corrected"]))
    model_scores = np.array([ranking["model_scores"][product_id] for product_id in ids], dtype="float64")
    best_score = float(model_scores.max()) if len(ids) else 0.0
    spread = float(model_scores.std()) or 1.0
    similarities = [signals[product_id]["semantic_similarity"] for product_id in ids]
    best_similarity = max((s for s in similarities if s is not None), default=None)
    rows = []
    for position, product_id in enumerate(ids, start=1):
        product, signal = by_id[product_id], signals[product_id]
        title_words = set(tokenize(product.get("title", "")))
        text_words = title_words | set(tokenize(" ".join(
            str(product.get(field) or "") for field in ("brand", "representation_text", "description"))))
        brand = _brand_words(product)
        similarity = signal["semantic_similarity"]
        rows.append((
            position,
            ranking["retrieval"][product_id],
            ranking["reranker"][product_id],
            ranking["model_scores"][product_id],
            ranking["model_scores"][product_id] - best_score,
            (ranking["model_scores"][product_id] - model_scores.mean()) / spread,
            _rank(signal["keyword_rank"]),
            float(signal["keyword_rank"] is not None),
            _rank(signal["semantic_rank"]),
            float(signal["semantic_rank"] is not None),
            math.nan if similarity is None else similarity,
            math.nan if similarity is None or best_similarity is None else similarity - best_similarity,
            float("fuzzy" in match_sources[product_id]),
            float(context["corrected"].strip().lower() != context["query"].strip().lower()),
            float(len(context["variations"])),
            float(len(tokenize(context["query"]))),
            _share(terms, title_words),
            _share(terms, text_words),
            float(bool(brand) and all(word in query_words for word in brand)),
            float(len(title_words)),
            float(len(ids)),
        ))
    return list(ids), np.asarray(rows, dtype="float32").reshape(len(ids), len(FEATURE_NAMES))

"""Plain facts about why a product ranked where it did.

Every search already computes these numbers; this keeps them per result so
the page can answer "why this result?" instead of discarding them.
"""
from src.keyword_search.bm25 import tokenize
from src.search.ranking import RERANKER_WEIGHT, RETRIEVAL_WEIGHT
from src.search.typos import STOP_WORDS

WEIGHTS = {"retrieval": RETRIEVAL_WEIGHT, "reranker": RERANKER_WEIGHT}


def product_words(product):
    text = " ".join(str(product.get(field) or "") for field in ("title", "brand", "representation_text", "description"))
    return set(tokenize(text))


def matched_terms(query, product):
    """Query words, minus filler words, that appear in the product's text."""
    words = product_words(product)
    return [word for word in dict.fromkeys(tokenize(query))
            if word not in STOP_WORDS and len(word) > 1 and word in words]


def rounded(value, digits=3):
    return None if value is None else round(float(value), digits)


def explanation(*, query, product, retrieval_rank, reranker_rank, reranker_score,
                blended_score, candidate_count, keyword_rank=None, semantic_rank=None,
                semantic_similarity=None, spelling_match=False, provider_rank=None):
    """One result's explanation; absent signals are None so the page can skip them.

    The page shows each result's own position, because filters applied after
    ranking can remove results in between."""
    return {
        "candidateCount": candidate_count,
        "matchedTerms": matched_terms(query, product),
        "keywordRank": keyword_rank,
        "semanticRank": semantic_rank,
        "semanticSimilarity": rounded(semantic_similarity),
        "spellingMatch": spelling_match,
        "providerRank": provider_rank,
        "retrievalRank": retrieval_rank,
        "rerankerRank": reranker_rank,
        "rerankerScore": rounded(reranker_score, 2),
        "blendedScore": rounded(blended_score, 5),
        "weights": WEIGHTS,
    }

"""Plain facts about why a product ranked where it did.

Every search already computes these numbers; this keeps them per result so
the page can answer "why this result?" instead of discarding them.
"""
from dataclasses import dataclass
from typing import Optional

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


@dataclass(frozen=True)
class RankSignals:
    """The numbers that placed one result; None means that signal did not apply."""
    retrieval_rank: int
    reranker_rank: int
    reranker_score: float
    blended_score: float
    candidate_count: int
    keyword_rank: Optional[int] = None
    semantic_rank: Optional[int] = None
    semantic_similarity: Optional[float] = None
    spelling_match: bool = False
    provider_rank: Optional[int] = None


def explanation(query, product, signals):
    """One result's explanation; absent signals are None so the page can skip them.

    The page shows each result's own position, because filters applied after
    ranking can remove results in between."""
    return {
        "candidateCount": signals.candidate_count,
        "matchedTerms": matched_terms(query, product),
        "keywordRank": signals.keyword_rank,
        "semanticRank": signals.semantic_rank,
        "semanticSimilarity": rounded(signals.semantic_similarity),
        "spellingMatch": signals.spelling_match,
        "providerRank": signals.provider_rank,
        "retrievalRank": signals.retrieval_rank,
        "rerankerRank": signals.reranker_rank,
        "rerankerScore": rounded(signals.reranker_score, 2),
        "blendedScore": rounded(signals.blended_score, 5),
        "weights": WEIGHTS,
    }

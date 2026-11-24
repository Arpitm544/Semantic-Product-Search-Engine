"""'Why this result?': each ranked product carries the numbers that placed it."""
from unittest.mock import Mock

import numpy as np

from api.ranking_service import CandidateRanker
from src.search.explanations import RankSignals, explanation, matched_terms
from src.search.product_search import ProductSearch
from src.search.ranking import RERANKER_WEIGHT, RETRIEVAL_WEIGHT, blend_ranks


PRODUCTS = [
    {"id": "a", "title": "Wired earbuds", "representation_text": "wired earbuds audio"},
    {"id": "b", "title": "Wireless headphones", "representation_text": "wireless bluetooth headphones"},
    {"id": "c", "title": "Noise cancelling headphones", "representation_text": "noise cancelling headphones travel"},
]


class Semantic:
    """Meaning search that likes the travel headphones best."""
    def search(self, query, top_k=10):
        return [(PRODUCTS[2], 0.81), (PRODUCTS[1], 0.64)][:top_k]


def reranker():
    model = Mock()
    model.predict.side_effect = lambda pairs, **_: [
        {"wireless bluetooth headphones": 3.0, "noise cancelling headphones travel": 9.5}.get(text, -2.0)
        for _, text in pairs
    ]
    return model


def test_matched_terms_skip_filler_words_and_keep_query_order():
    product = {"title": "Sony wireless headphones", "representation_text": "bluetooth over ear"}
    assert matched_terms("show me wireless sony headphones for travel", product) == ["wireless", "sony", "headphones"]
    assert matched_terms("comfy cans", product) == []


def test_ranking_weights_are_shared_with_the_explanation():
    assert (RETRIEVAL_WEIGHT, RERANKER_WEIGHT) == (0.25, 0.75)
    assert blend_ranks({"x": 1}, {"x": 2}) == {"x": 0.25 / 61 + 0.75 / 62}
    details = explanation("q", {}, RankSignals(retrieval_rank=1, reranker_rank=2, reranker_score=1.23456,
                                               blended_score=0.0162, candidate_count=5))
    assert details["weights"] == {"retrieval": 0.25, "reranker": 0.75}
    assert details["rerankerScore"] == 1.23 and details["semanticRank"] is None


def test_catalog_results_explain_keyword_meaning_and_reranker():
    engine = ProductSearch(PRODUCTS, Semantic(), reranker())
    results = engine.search("headphones", fuzzy=False)["results"]
    assert [item["id"] for item in results][:2] == ["c", "b"]

    top = results[0]["explanation"]
    assert top["matchedTerms"] == ["headphones"]
    assert top["semanticRank"] == 1 and top["semanticSimilarity"] == 0.81
    assert top["keywordRank"] in (1, 2)
    assert top["rerankerRank"] == 1 and top["rerankerScore"] == 9.5
    assert top["candidateCount"] == len(results)
    assert top["spellingMatch"] is False and top["providerRank"] is None
    # The explanation's numbers reproduce the result's blended score.
    assert top["blendedScore"] == round(results[0]["score"], 5)
    assert results[0]["score"] == blend_ranks({"c": top["retrievalRank"]}, {"c": top["rerankerRank"]})["c"]


def test_spelling_matches_are_explained():
    engine = ProductSearch(PRODUCTS, None, reranker())
    results = engine.search("headphnes")["results"]
    assert results and all(item["explanation"]["spellingMatch"] for item in results)
    assert results[0]["explanation"]["semanticRank"] is None


def test_existing_method_signatures_still_return_two_values():
    engine = ProductSearch(PRODUCTS, Semantic(), reranker())
    ids, sources = engine.find_candidates(["headphones"], "headphones")
    assert set(ids) == {"b", "c"} and "semantic" in sources["c"]
    ranked, scores = engine.rank_candidates("headphones", ids)
    assert ranked[0] == "c" and set(scores) == set(ids)


def test_shop_results_explain_shop_order_meaning_and_reranker():
    encoder = Mock()
    encoder.encode.return_value = np.array([[1.0, 0.0], [0.6, 0.8], [1.0, 0.0]])
    model = Mock()
    model.predict.return_value = np.array([0.5, 4.0])
    shop_products = [{"title": "Earbuds case"}, {"title": "Wireless earbuds"}]
    ranked = CandidateRanker(encoder, model).rank("wireless earbuds", shop_products)
    assert [item["title"] for item in ranked] == ["Wireless earbuds", "Earbuds case"]
    first = ranked[0]["explanation"]
    assert first["providerRank"] == 2 and first["semanticRank"] == 1 and first["semanticSimilarity"] == 1.0
    assert first["rerankerRank"] == 1 and first["matchedTerms"] == ["wireless", "earbuds"]
    assert first["candidateCount"] == 2

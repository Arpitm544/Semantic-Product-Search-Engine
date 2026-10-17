"""Behavior checks for misspellings, ambiguous corrections, and held-out data."""

import random
import unittest
from unittest.mock import patch

from src.search.hybrid import HybridSearch
from src.search.typos import CatalogSpelling, edit_distance
from src.semantic.evaluate_typos import retrieval_metrics
from src.semantic.fine_tune import grouped_batches
from src.semantic.prepare_training import prepare_data, typo_query


PRODUCTS = [
    {"id": 1, "title": "Samsung Galaxy", "category": "phones",
     "representation_text": "samsung galaxy smartphone android"},
    {"id": 2, "title": "Apple iPhone15", "category": "phones",
     "representation_text": "apple iphone15 smartphone"},
    {"id": 3, "title": "Cat Food", "category": "groceries",
     "representation_text": "cat food meals nutrition"},
]


class TestSpelling(unittest.TestCase):
    def test_adjacent_transposition_and_fallback_match(self):
        self.assertEqual(edit_distance("iphnoe", "iphone"), 1)
        with patch("src.search.typos.OSA", None):
            self.assertEqual(edit_distance("iphnoe", "iphone"), 1)
            self.assertEqual(edit_distance("headphons", "headphones"), 1)

    def test_unknown_word_suggestion_preserves_known_words_and_codes(self):
        spelling = CatalogSpelling(["samsung", "galaxy", "iphone15", "cat", "car"])
        corrected, corrections = spelling.correct("samsng GALAXY iphone15 cat s24")
        self.assertEqual(corrected, "samsung GALAXY iphone15 cat s24")
        self.assertEqual(len(corrections), 1)

    def test_ambiguous_candidate_is_not_replaced(self):
        self.assertIsNone(CatalogSpelling(["laptop", "laptoe"]).suggestion("lapton"))

    def test_arbitrary_text_is_not_forced_to_catalog_terms(self):
        self.assertIsNone(CatalogSpelling(["samsung"]).suggestion("zzzzzz"))
        self.assertIsNone(CatalogSpelling(["samsung"]).suggestion("please"))


class TestHybrid(unittest.TestCase):
    def test_fuzzy_recovers_a_query_with_no_exact_matches(self):
        engine = HybridSearch(PRODUCTS)
        payload = engine.search("samsng")
        self.assertEqual(payload["query"], "samsng")
        self.assertEqual(payload["correctedQuery"], "samsung")
        self.assertEqual(payload["results"][0]["id"], 1)
        self.assertIn("fuzzy", payload["results"][0]["matchSources"])
        self.assertEqual(payload["searchMode"], "bm25-fuzzy")

    def test_original_spelling_opt_out(self):
        payload = HybridSearch(PRODUCTS).search("samsng", fuzzy=False)
        self.assertIsNone(payload["correctedQuery"])
        self.assertEqual(payload["results"], [])

    def test_semantic_results_are_combined_and_deduplicated(self):
        class Semantic:
            def search(self, query, top_k):
                return [(PRODUCTS[2], 0.8), (PRODUCTS[0], 0.5)][:top_k]

        engine = HybridSearch(PRODUCTS, Semantic())
        payload = engine.search("cat")
        self.assertEqual(payload["results"][0]["id"], 3)
        self.assertEqual(payload["results"][0]["matchSources"], ["keyword", "semantic"])
        self.assertEqual(len({p["id"] for p in payload["results"]}), len(payload["results"]))

    def test_blank_queries_do_not_return_the_entire_catalog(self):
        self.assertEqual(HybridSearch(PRODUCTS).search(" ?! ")["results"], [])


class TestTrainingProtocol(unittest.TestCase):
    def test_families_and_curated_eval_products_never_enter_training(self):
        products = [
            {"id": i, "title": f"Product name{i}", "category": f"category{i % 3}"}
            for i in range(20)
        ]
        products.append({"id": 20, "title": "Product name0", "category": "category0"})
        queries = [{"query_id": "q1", "query": "Product name0", "relevant_doc_ids": [0]}]
        data, manifest = prepare_data(products, queries)
        train_ids = {row["product_id"] for row in data["train"]}
        held_ids = {i for split in ("validation", "test")
                    for row in data[split] for i in row["relevant_doc_ids"]}
        self.assertFalse(train_ids & held_ids)
        self.assertNotIn(0, train_ids)
        self.assertNotIn(20, train_ids)
        self.assertEqual(prepare_data(products, queries), (data, manifest))
        self.assertEqual(prepare_data(list(reversed(products)), queries), (data, manifest))
        train_queries = {row["query"].lower() for row in data["train"]}
        held_queries = {row["query"].lower() for split in ("validation", "test") for row in data[split]}
        self.assertFalse(train_queries & held_queries)

    def test_batches_do_not_treat_same_category_as_negative(self):
        rows = [{"negative_group": str(i % 4)} for i in range(40)]
        batches = grouped_batches(rows, 4, 42)
        used = []
        for batch in batches:
            self.assertGreaterEqual(len(batch), 2)
            self.assertEqual(len(batch), len({rows[i]["negative_group"] for i in batch}))
            used.extend(batch)
        self.assertEqual(len(used), len(set(used)))
        self.assertEqual(len(used), 40)

    def test_esci_batches_consume_uneven_remainder(self):
        rows = [{"negative_group": group} for group in ["a"] * 15 + ["b"] * 2]
        batches = grouped_batches(rows, 4, 42, include_remainder=True)
        used = [index for batch in batches for index in batch]
        self.assertEqual(sorted(used), list(range(len(rows))))
        self.assertTrue(all(1 <= len(batch) <= 4 for batch in batches))

    def test_metric_labels_follow_requested_cutoff(self):
        metrics = retrieval_metrics([99, 1], [1], k=1)
        self.assertEqual(metrics["recall@1"], 0)
        self.assertEqual(metrics["hit_rate@1"], 0)
        self.assertNotIn("recall@5", metrics)

    def test_typo_generation_keeps_model_number(self):
        for kind in ("deletion", "transposition", "substitution", "repetition"):
            changed = typo_query("Samsung Galaxy S24", kind, random.Random(42))
            self.assertNotEqual(changed, "Samsung Galaxy S24")
            self.assertIn("S24", changed)

    def test_hit_rate_is_not_mistaken_for_recall(self):
        metrics = retrieval_metrics([1, 99, 98], [1, 2, 3])
        self.assertAlmostEqual(metrics["recall@5"], 1 / 3)
        self.assertEqual(metrics["hit_rate@5"], 1.0)


if __name__ == "__main__":
    unittest.main()

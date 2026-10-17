"""Check ESCI split integrity, hard-negative protection, and loss gradients."""

import unittest

from src.keyword_search.bm25 import fit_bm25, search_bm25
from src.semantic.prepare_esci import (
    choose_training_pairs, normalize_query, select_splits, group_judgments, evaluation_records,
)
from src.semantic.train_esci import (
    contrastive_loss, negative_mask, validate_training_rows,
)


def group(query, grades):
    return {"query": query, "query_ids": {"1"}, "grades": grades}


class TestESCISplits(unittest.TestCase):
    def test_query_families_ignore_case_spacing_and_punctuation(self):
        self.assertEqual(normalize_query("  Wireless-Headphones! "), "wireless headphones")
        self.assertEqual(normalize_query("Ｗｉｒｅｌｅｓｓ headphones"), "wireless headphones")

    def test_official_test_query_alias_cannot_enter_training(self):
        train = {
            f"query {i}": group(f"Query {i}", {f"p{i}": 3, f"n{i}": 0})
            for i in range(20)
        }
        import pandas as pd
        examples = pd.DataFrame([
            {"query": "Query 1", "product_id": "p1", "esci_label": "E", "query_id": 1},
            {"query": "  Ｑｕｅｒｙ-1! ", "product_id": "p1", "esci_label": "E", "query_id": 2},
        ])
        train.update(group_judgments(examples.iloc[:1]))
        test = group_judgments(examples.iloc[1:])
        training, reserved, validation, selected_test = select_splits(train, test, 2, 1, 42)
        self.assertNotIn("query 1", training)
        self.assertNotIn("query 1", reserved)
        self.assertFalse(set(training) & set(reserved))
        self.assertTrue(set(validation) <= set(reserved))
        self.assertEqual(selected_test, ["query 1"])

    def test_evaluation_keeps_substitute_and_complement_labels(self):
        groups = {"phone": group("phone", {"e": 3, "s": 2, "c": 1, "i": 0})}
        for row in evaluation_records(groups, ["phone"], 42):
            self.assertEqual(set(row["relevant_doc_ids"]), {"e", "s", "c"})

    def test_only_exact_positives_and_irrelevant_negatives_are_selected(self):
        groups = {
            "wireless headphones": group("wireless headphones", {
                "exact": 3, "substitute": 2, "complement": 1, "irrelevant": 0,
            }),
        }
        pairs = choose_training_pairs(groups, list(groups), 1, {"validation query"}, 42)
        self.assertEqual(pairs[0]["product_id"], "exact")
        self.assertEqual(pairs[0]["negative_id"], "irrelevant")
        self.assertEqual(set(pairs[0]["relevant_product_ids"]), {"exact", "substitute", "complement"})
        self.assertNotEqual(pairs[0]["typo"], pairs[0]["query"])

    def test_held_query_is_rejected_at_training_time(self):
        manifest = {
            "reserved_validation_families": ["held query"], "official_test_families": [],
            "clean_training_pairs": 1, "augmented_training_pairs": 1,
        }
        row = {
            "query": "held query", "query_family": "held query", "kind": "clean",
            "product_id": "positive", "negative_id": "negative",
            "relevant_product_ids": ["positive"],
        }
        with self.assertRaisesRegex(ValueError, "held-out"):
            validate_training_rows([row], manifest, [])


class TestMaskedLoss(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"product_id": "p1", "negative_id": "n1", "relevant_product_ids": ["p1", "p2"]},
            {"product_id": "p2", "negative_id": "n2", "relevant_product_ids": ["p2"]},
        ]

    def test_other_relevant_products_are_masked_but_target_is_kept(self):
        mask = negative_mask(self.rows)
        self.assertTrue(mask[0][0])
        self.assertFalse(mask[0][1])
        self.assertTrue(mask[0][2])
        self.assertTrue(mask[1][1])

    def test_relevant_product_cannot_be_used_as_own_hard_negative(self):
        self.rows[0]["negative_id"] = "p2"
        with self.assertRaisesRegex(ValueError, "hard negative"):
            negative_mask(self.rows)

    def test_loss_is_finite_and_propagates_gradients(self):
        import torch

        query = torch.tensor([[1., 0.], [0., 1.]], requires_grad=True)
        positive = torch.tensor([[0.8, 0.2], [0.2, 0.8]], requires_grad=True)
        negative = torch.tensor([[0.4, 0.6], [0.6, 0.4]], requires_grad=True)
        loss = contrastive_loss(query, positive, negative, self.rows)
        self.assertTrue(torch.isfinite(loss))
        loss.backward()
        for embedding in (query, positive, negative):
            self.assertIsNotNone(embedding.grad)
            self.assertTrue(torch.isfinite(embedding.grad).all())


class TestBM25Postings(unittest.TestCase):
    def test_saved_legacy_index_matches_new_index_with_repeated_query_terms(self):
        products = [
            {"id": 1, "representation_text": "samsung phone"},
            {"id": 2, "representation_text": "samsung phone phone"},
            {"id": 3, "representation_text": "apple phone"},
        ]
        index = fit_bm25(products)
        expected = search_bm25(index, "phone samsung phone", 10)
        self.assertEqual([p["id"] for p, _ in expected], [2, 1, 3])
        index.pop("postings")
        self.assertEqual(search_bm25(index, "phone samsung phone", 10), expected)


if __name__ == "__main__":
    unittest.main()

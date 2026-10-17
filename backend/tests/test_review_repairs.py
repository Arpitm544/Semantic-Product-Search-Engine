"""Regression checks for catalog consistency and serving/evaluation contracts."""
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import Mock, patch

from api import main as api
from src.baseline.bm25 import fit_bm25, search_bm25
from src.data import amazon_mongo
from src.search.amazon import AmazonSearch


class TestCatalogRepairs(unittest.TestCase):
    def test_catalog_change_during_read_is_rejected_even_at_same_count(self):
        first = {"status": "ready", "sha256": "old", "product_count": 1}
        second = {**first, "sha256": "new"}
        database = Mock()
        database.__getitem__ = Mock(return_value=Mock())
        database[amazon_mongo.COLLECTION].find.return_value.sort.return_value = [{"id": "esci:1"}]
        with patch.object(amazon_mongo, "database", return_value=database), \
                patch.object(amazon_mongo, "version", side_effect=[first, second]):
            with self.assertRaisesRegex(ValueError, "changed while loading"):
                amazon_mongo.load_products()

    def test_import_rejects_empty_or_nonlist_input_before_database_access(self):
        script = Path(api.PROJECT_ROOT) / "scripts/import_amazon_mongo.py"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "products.json"
            for value in ([], {}, None):
                source.write_text(json.dumps(value))
                with patch("sys.argv", [str(script), "--source", str(source)]), \
                        patch.object(amazon_mongo, "database") as database:
                    with self.assertRaisesRegex(ValueError, "nonempty list"):
                        runpy.run_path(str(script), run_name="__main__")
                    database.assert_not_called()

    def test_shared_configuration_reads_env_without_overriding_exports(self):
        config_source = (api.PROJECT_ROOT / "src/config.py").read_text()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            config = root / "src/config.py"
            config.write_text(config_source)
            (root / ".env").write_text("MONGO_DB_NAME=from_file\nMONGO_URI=mongodb://file:27017/\n")
            with patch.dict(os.environ, {"MONGO_URI": "mongodb://shell:27017/"}):
                os.environ.pop("MONGO_DB_NAME", None)
                loaded = runpy.run_path(str(config))
                self.assertEqual(loaded["MONGO_DB_NAME"], "from_file")
                self.assertEqual(loaded["MONGO_URI"], "mongodb://shell:27017/")


class TestSearchRepairs(unittest.TestCase):
    def test_negative_keyword_limit_returns_no_results(self):
        index = fit_bm25([{"id": 1, "title": "phone"}, {"id": 2, "title": "phone"}])
        self.assertEqual(search_bm25(index, "phone", -1), [])

    def test_full_text_model_label_and_expansion_provenance(self):
        product = {"id": "p", "title": "Headphones", "representation_text": "headphones waterproof"}
        semantic = Mock(model_name="custom-checkpoint")
        semantic.search.return_value = []
        reranker = Mock()
        reranker.predict.return_value = [1.0]
        engine = AmazonSearch([product], semantic, reranker)
        self.assertEqual(engine.search("waterproof", fuzzy=False)["results"][0]["id"], "p")
        engine.spelling = Mock()
        engine.spelling.correct.return_value = ("headphones", [{"from": "headphons", "to": "headphones"}])
        engine.spelling.alternatives.return_value = ["headphons", "headphones"]
        with patch.object(engine.hybrid, "search", wraps=engine.hybrid.search) as search:
            result = engine.search("headphons")
        self.assertEqual(result["semanticModel"], "custom-checkpoint")
        self.assertTrue(all(call.kwargs["fuzzy"] is False for call in search.call_args_list))
        self.assertIn("fuzzy", result["results"][0]["matchSources"])

    def test_dashboard_restores_saved_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ("eval.json", "baseline.json", "semantic.json")]
            values = [[{"query": "phone"}], {"map": .2}, {"map": .3}]
            for path, value in zip(paths, values):
                path.write_text(json.dumps(value))
            with patch.object(api, "load_products", return_value=[{"id": "p"}]), \
                    patch.object(api, "EVAL_PATH", paths[0]), \
                    patch.object(api, "BM25_REPORT_PATH", paths[1]), \
                    patch.object(api, "SEMANTIC_REPORT_PATH", paths[2]):
                data = api.dashboard_data()
            self.assertEqual(data["evalQueries"], values[0])
            self.assertEqual(data["benchmark"]["bm25"], values[1])
            self.assertEqual(data["benchmark"]["semantic"], values[2])


class TestEvaluationRepairs(unittest.TestCase):
    def test_corrupt_or_missing_cache_manifest_is_stale(self):
        from src.semantic.evaluate_typos import cache_matches
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "signature.json"
            self.assertFalse(cache_matches(path, {"catalog": "new"}))
            path.write_text('{"catalog":')
            self.assertFalse(cache_matches(path, {"catalog": "new"}))
            path.write_text('{"catalog": "old"}')
            self.assertFalse(cache_matches(path, {"catalog": "new"}))
            path.write_text('{"catalog": "new"}')
            self.assertTrue(cache_matches(path, {"catalog": "new"}))

    def test_legacy_evaluator_rebuilds_warms_and_retrieves_full_map_ranking(self):
        from src.semantic import evaluate_semantic as evaluation
        products = [{"id": i, "title": f"product {i}"} for i in range(12)]
        engine = Mock()
        engine.search.return_value = [(product, 1.0) for product in products]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.json"
            path.write_text(json.dumps([{"query": "product", "relevant_doc_ids": [11]}]))
            with patch.object(evaluation, "load_cleaned_products", return_value=products), \
                    patch.object(evaluation, "SemanticVectorSearch", return_value=engine) as constructor:
                report = evaluation.evaluate_semantic(path, Path(directory) / "report.json")
            constructor.assert_called_once_with()
            engine.fit.assert_called_once_with(products)
            engine.load.assert_not_called()
            self.assertEqual(engine.search.call_args_list[0].kwargs["top_k"], 1)
            self.assertEqual(engine.search.call_args_list[1].kwargs["top_k"], 12)
            self.assertAlmostEqual(report["map"], 1 / 12)
            self.assertIn("legacy", report["benchmark"])

    def test_nonfinite_learning_rate_rejected_before_training(self):
        from src.semantic import train_esci
        for rate in ("nan", "inf", "-inf"):
            with patch("sys.argv", ["train_esci", "--learning-rate=" + rate]):
                with self.assertRaises(SystemExit) as error:
                    train_esci.main()
                self.assertEqual(error.exception.code, 2)


class TestTrainingPublication(unittest.TestCase):
    def test_failed_index_build_can_be_retried_and_completed_output_is_published(self):
        from src.semantic.fine_tune import save_candidate
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate"
            model, engine = Mock(), Mock()
            model.save_pretrained.side_effect = lambda path: (Path(path) / "modules.json").write_text("[]")
            with patch("src.semantic.vector_search.SemanticVectorSearch", return_value=engine):
                engine.save.side_effect = RuntimeError("index failed")
                with self.assertRaisesRegex(RuntimeError, "index failed"):
                    save_candidate(model, [{"id": 1}], output, {"steps": 1})
                self.assertFalse(output.exists())
                self.assertEqual(list(Path(directory).iterdir()), [])
                def save_index(index, mapping):
                    index.write_bytes(b"vectors")
                    mapping.write_bytes(b"metadata")
                engine.save.side_effect = save_index
                save_candidate(model, [{"id": 1}], output, {"steps": 1})
            self.assertTrue((output / "modules.json").exists())
            self.assertTrue((output / "faiss_index.bin").exists())
            self.assertEqual(json.loads((output / "training_report.json").read_text()), {"steps": 1})

    def test_resume_rejects_changed_jsonl_with_unchanged_manifest(self):
        import hashlib
        from src.semantic import train_esci
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "data"
            data.mkdir()
            manifest = {"seed": 42, "clean_training_pairs": 2, "augmented_training_pairs": 2,
                        "reserved_validation_families": [], "official_test_families": []}
            (data / "manifest.json").write_text(json.dumps(manifest))
            rows = [{"query": f"query {i}", "query_family": f"query {i}", "kind": "clean",
                     "negative_group": str(i), "product_id": f"p{i}", "negative_id": f"n{i}",
                     "relevant_product_ids": [f"p{i}"]} for i in range(2)]
            (data / "train.jsonl").write_text("\n".join(map(json.dumps, rows)) + "\n")
            for name in ("validation.jsonl", "test.jsonl"):
                (data / name).write_text("")
            old_config = {
                "dataset_manifest_sha256": hashlib.sha256((data / "manifest.json").read_bytes()).hexdigest(),
                "dataset_files_sha256": {name: hashlib.sha256((data / name).read_bytes()).hexdigest()
                    for name in ("train.jsonl", "validation.jsonl", "test.jsonl")},
                "base_model": "all-MiniLM-L6-v2", "epochs": 1, "batch_size": 32,
                "learning_rate": 2e-5, "max_length": 128, "seed": 42, "total_steps": 1,
            }
            rows[0]["query"] = "changed training query"
            (data / "train.jsonl").write_text("\n".join(map(json.dumps, rows)) + "\n")
            model = Mock()
            with patch("sys.argv", ["train_esci", "--data-dir", str(data), "--output-dir", str(Path(directory) / "model"), "--resume"]), \
                    patch("sentence_transformers.SentenceTransformer", return_value=model), \
                    patch("torch.set_num_threads"), patch("torch.manual_seed"), \
                    patch("torch.optim.AdamW"), patch("torch.optim.lr_scheduler.LambdaLR"), \
                    patch("torch.load", return_value={"config": old_config}):
                with self.assertRaises(SystemExit) as error:
                    train_esci.main()
                self.assertEqual(error.exception.code, 2)
                model.load_state_dict.assert_not_called()

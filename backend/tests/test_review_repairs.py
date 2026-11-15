"""Regression checks for catalog consistency and serving/evaluation contracts."""
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import Mock, patch

from api import main as api
from src.keyword_search.bm25 import fit_bm25, search_bm25
from src.data import catalog as amazon_mongo
from src.search.product_search import ProductSearch


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
        script = Path(api.PROJECT_ROOT) / "scripts/import_catalog.py"
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
        engine = ProductSearch([product], semantic, reranker)
        self.assertEqual(engine.search("waterproof", fuzzy=False)["results"][0]["id"], "p")
        engine.spelling = Mock()
        engine.spelling.correct.return_value = ("headphones", [{"from": "headphons", "to": "headphones"}])
        engine.spelling.alternatives.return_value = ["headphons", "headphones"]
        with patch.object(engine.hybrid, "search", wraps=engine.hybrid.search) as search:
            result = engine.search("headphons")
        self.assertEqual(result["semanticModel"], "custom-checkpoint")
        self.assertTrue(all(call.kwargs["fuzzy"] is False for call in search.call_args_list))
        self.assertIn("fuzzy", result["results"][0]["matchSources"])



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


    def test_nonfinite_learning_rate_rejected_before_training(self):
        from src.semantic import train_esci
        for rate in ("nan", "inf", "-inf"):
            with patch("sys.argv", ["train_esci", "--learning-rate=" + rate]):
                with self.assertRaises(SystemExit) as error:
                    train_esci.main()
                self.assertEqual(error.exception.code, 2)




class TestRelocationAndStartup(unittest.TestCase):

    def test_old_index_metadata_still_uses_its_model_reference(self):
        import pickle
        import pytest
        faiss = pytest.importorskip("faiss")
        from src.semantic.vector_search import SemanticVectorSearch
        with tempfile.TemporaryDirectory() as directory:
            index, mapping = Path(directory) / "index.bin", Path(directory) / "map.pkl"
            faiss.write_index(faiss.IndexFlatIP(2), str(index))
            mapping.write_bytes(pickle.dumps({"model_name": "legacy-model", "products": [], "dimension": 2}))
            self.assertEqual(SemanticVectorSearch.load(index, mapping).model_name, "legacy-model")

    def test_import_in_progress_is_retryable_but_missing_catalog_is_not(self):
        database = Mock()
        database.__getitem__ = Mock(return_value=Mock())
        collection = database['catalog_manifests']
        with patch.object(amazon_mongo, 'database', return_value=database):
            collection.find_one.return_value = {'status': 'importing'}
            with self.assertRaises(amazon_mongo.CatalogUpdatingError):
                amazon_mongo.version()
            collection.find_one.return_value = None
            with self.assertRaises(ValueError) as error:
                amazon_mongo.version()
            self.assertNotIsInstance(error.exception, amazon_mongo.CatalogUpdatingError)

    def test_startup_recovers_after_catalog_import(self):
        from threading import Event
        with patch.object(api, '_search_ready', Event()), patch.object(api, '_search_error', None), \
                patch.object(api, 'sleep') as wait, \
                patch.object(api, 'get_search_engine', side_effect=[
                    amazon_mongo.CatalogUpdatingError('importing'),
                    amazon_mongo.CatalogUpdatingError('changed during loading'), Mock(),
                ]) as initialize:
            api.initialize_search(max_attempts=3)
            self.assertTrue(api._search_ready.is_set())
            self.assertIsNone(api._search_error)
            self.assertEqual(initialize.call_count, 3)
            self.assertEqual(wait.call_count, 2)

    def test_startup_retry_is_bounded_and_does_not_hide_model_errors(self):
        from threading import Event
        for error, expected_attempts in [(amazon_mongo.CatalogUpdatingError('importing'), 3),
                                         (FileNotFoundError('missing encoder'), 1)]:
            with patch.object(api, '_search_ready', Event()), patch.object(api, '_search_error', None), \
                    patch.object(api, 'sleep') as wait, \
                    patch.object(api, 'get_search_engine', side_effect=error) as initialize:
                api.initialize_search(max_attempts=3)
                self.assertFalse(api._search_ready.is_set())
                self.assertIn(str(error), api._search_error)
                self.assertEqual(initialize.call_count, expected_attempts)
                self.assertEqual(wait.call_count, expected_attempts - 1)

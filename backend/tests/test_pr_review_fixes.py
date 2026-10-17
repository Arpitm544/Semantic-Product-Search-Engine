"""Regression checks for PR review edge cases without model downloads."""
from collections import Counter
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
from threading import Event
import unittest
from unittest.mock import MagicMock, Mock, patch

from api import dashboard, main as api, search_service
from src.search.product_search import FrequencySpelling, ProductSearch
from src.search.typos import CatalogSpelling
from src.semantic import download_esci
from tests import metrics_helpers as metrics


class TestReviewFixes(unittest.TestCase):
    def test_preparation_reads_boolean_small_version_parquet_filter(self):
        from argparse import Namespace
        import pandas as pd
        from src.semantic import prepare_esci

        class LabelsLoaded(Exception):
            pass

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pd.DataFrame({
                'query': ['coat', 'other', 'foreign'], 'query_id': [1, 2, 3],
                'product_id': ['p1', 'p2', 'p3'], 'esci_label': ['E'] * 3,
                'split': ['train'] * 3, 'product_locale': ['us', 'us', 'es'],
                'small_version': [True, False, True],
            }).to_parquet(root / 'shopping_queries_dataset_examples.parquet')

            def inspect_labels(labels):
                self.assertEqual(labels['product_id'].tolist(), ['p1'])
                raise LabelsLoaded()

            with patch.object(prepare_esci, 'group_judgments', side_effect=inspect_labels):
                with self.assertRaises(LabelsLoaded):
                    prepare_esci.prepare_dataset(Namespace(raw_dir=root, output_dir=root / 'prepared',
                                                          pairs=1, validation_queries=1, test_queries=1), Mock())

    def test_metrics_reject_nonpositive_cutoffs_and_deduplicate_rankings(self):
        for metric in (metrics.precision_at_k, metrics.recall_at_k,
                       metrics.dcg_at_k, metrics.ndcg_at_k):
            for k in (-1, 0):
                self.assertEqual(metric([1, 1, 2], {1}, k), 0)
            self.assertEqual(metric([9, 9, 1, 1, 2], {1, 2}, 3),
                             metric([9, 1, 2], {1, 2}, 3))
        for metric in (metrics.average_precision, metrics.reciprocal_rank):
            self.assertEqual(metric([9, 9, 1, 1, 2], {1, 2}), metric([9, 1, 2], {1, 2}))
            self.assertLessEqual(metric([1, 1, 1], {1}), 1)

    def test_short_word_spelling_retains_ambiguity_and_long_word_safeguards(self):
        for spelling in (CatalogSpelling(['coat']), FrequencySpelling(Counter(coat=8))):
            self.assertEqual(spelling.correct('cozt')[0], 'coat')
            self.assertEqual(spelling.correct('caot')[0], 'coat')
            self.assertEqual(spelling.correct('cot')[0], 'cot')
        for spelling in (CatalogSpelling(['coat', 'cost']),
                         FrequencySpelling(Counter(coat=8, cost=8))):
            self.assertIsNone(spelling.suggestion('cozt'))
        self.assertIsNone(CatalogSpelling(['planet']).suggestion('plxnyt'))

    def test_missing_and_partial_stock_are_unknown_but_zero_is_known(self):
        for products, expected in (([{'id': 'a'}], None),
                                   ([{'stock': 2}, {'stock': None}], None),
                                   ([{'stock': 0}, {'stock': 2}], 2),
                                   ([{'stock': 0}], 0)):
            with patch.object(dashboard, 'load_products', return_value=products):
                self.assertEqual(dashboard.dashboard_data()['totalStock'], expected)

    def test_keyword_only_search_metadata_does_not_advertise_semantics(self):
        payload = ProductSearch([], None, Mock()).search('')
        self.assertEqual(payload['searchMode'], 'expanded-keyword-reranked')
        self.assertIsNone(payload['semanticModel'])

    def test_reload_failure_clears_health_and_next_search_can_recover(self):
        ready = Event()
        ready.set()
        old, new = Mock(), Mock()
        new.search.return_value = {'results': []}
        manifest = {'sha256': 'new', 'updated_at': '2'}
        def rebuild(*args):
            self.assertFalse(ready.is_set())
            self.assertEqual(api.check_health().status_code, 503)
            return Mock()
        with patch.object(api, '_search_ready', ready), \
                patch.object(search_service, '_search_ready', ready), \
                patch.object(search_service, '_search_error', None), \
                patch.object(search_service, '_search_engine', old), \
                patch.object(search_service, '_search_signature', ('old', '1', '', '')), \
                patch.object(search_service, 'version', return_value=manifest), \
                patch.object(search_service, 'load_products', side_effect=[ValueError('importing'), []]), \
                patch.object(search_service, 'load_semantic_search', side_effect=rebuild), \
                patch.object(search_service, 'load_reranker'), \
                patch.object(search_service, 'ProductSearch', return_value=new):
            self.assertEqual(api.search_products('coat').status_code, 503)
            self.assertFalse(ready.is_set())
            self.assertEqual(api.check_health().status_code, 503)
            self.assertEqual(api.search_products('coat'), {'results': []})
            self.assertTrue(ready.is_set())
            self.assertEqual(api.check_health().status_code, 200)

    def test_import_lock_excludes_another_writer_and_releases_on_failure(self):
        from pymongo.errors import DuplicateKeyError
        importer = runpy.run_path(str(api.PROJECT_ROOT / 'scripts/import_catalog.py'))
        database = MagicMock()
        locks = database.__getitem__.return_value
        locks.insert_one.side_effect = DuplicateKeyError('busy')
        with self.assertRaisesRegex(RuntimeError, 'locked'):
            with importer['catalog_import_lock'](database):
                self.fail('A second writer must not run')
        locks.delete_one.assert_not_called()
        locks.insert_one.side_effect = None
        with self.assertRaisesRegex(ValueError, 'write failed'):
            with importer['catalog_import_lock'](database):
                raise ValueError('write failed')
        owner = locks.insert_one.call_args.args[0]['owner']
        locks.delete_one.assert_called_once_with({'_id': importer['COLLECTION'], 'owner': owner})

    def test_importer_loads_dotenv_before_reading_database_and_collection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('scripts/import_catalog.py', 'src/config.py',
                         'src/data/catalog.py', 'src/data/db.py'):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(api.PROJECT_ROOT / name, target)
            (root / '.env').write_text('MONGO_URI=mongodb://from-file:27017/\n'
                                      'MONGO_DB_NAME=review_database\nMONGO_COLLECTION=review_collection\n')
            code = ('import runpy,sys; sys.path.insert(0,sys.argv[1]); '
                    'runpy.run_path(sys.argv[1]+"/scripts/import_catalog.py"); '
                    'from src import config; from src.data import catalog; '
                    'print(config.MONGO_URI,config.MONGO_DB_NAME,catalog.COLLECTION)')
            import os
            env = dict(os.environ, MONGO_URI='mongodb://from-shell:27017/')
            env.pop('MONGO_DB_NAME', None)
            env.pop('MONGO_COLLECTION', None)
            result = subprocess.run([sys.executable, '-c', code, str(root)],
                                    env=env, check=True, capture_output=True, text=True)
            self.assertEqual(result.stdout.strip(),
                             'mongodb://from-shell:27017/ review_database review_collection')

    def test_interrupted_manifest_publication_preserves_previous_revision(self):
        from argparse import Namespace
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            metadata = {'revision': 'a' * 40, 'files': {
                name: {'sha256': 'b' * 64, 'bytes': 1} for name in download_esci.FILES}}
            path = root / 'source.json'
            path.write_text(json.dumps(metadata))
            for name in ('LICENSE', 'NOTICE'):
                (root / name).touch()
            with patch.object(download_esci, 'download_verified'), \
                    patch.object(Path, 'replace', side_effect=OSError('disk failure')):
                with self.assertRaisesRegex(OSError, 'disk failure'):
                    download_esci.download_dataset(Namespace(output_dir=root, revision=None), Mock())
            self.assertEqual(json.loads(path.read_text()), metadata)
            with patch.object(download_esci, 'download_verified'):
                download_esci.download_dataset(Namespace(output_dir=root, revision=None), Mock())
            self.assertEqual(json.loads(path.read_text())['revision'], metadata['revision'])

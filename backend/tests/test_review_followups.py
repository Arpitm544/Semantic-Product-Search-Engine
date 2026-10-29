"""Regression checks for PR 12 review repairs, without model downloads."""
from collections import Counter
import gc
import hashlib
from pathlib import Path
import runpy
import shutil
import tempfile
from threading import Lock
import unittest
from unittest.mock import Mock, patch
import weakref

import numpy as np
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("authenticated_api")

from api import dashboard, main as api, search_service
from src.data import catalog
from src.search.hybrid import HybridSearch
from src.search.typos import CatalogSpelling, FrequencySpelling


class TestReviewFollowups(unittest.TestCase):
    def test_initialization_import_error_returns_503_and_can_retry(self):
        engine = Mock()
        engine.search.return_value = {'results': []}
        with patch.object(api._search_ready, 'is_set', return_value=False), \
                patch.object(api, '_search_error', 'Previous startup failure'), \
                patch.object(search_service, '_search_engine', None), \
                patch.object(api, 'get_search_engine', side_effect=[ImportError('Missing model dependency'), engine]):
            client = TestClient(api.app)
            response = client.get('/api/search?q=phone')
            self.assertEqual(response.status_code, 503)
            self.assertIn('Missing model dependency', response.json()['error'])
            self.assertEqual(client.get('/api/search?q=phone').status_code, 200)

    def test_readable_malformed_vector_caches_are_rebuilt(self):
        for payload in ({'vectors': [[1., 0.]]}, {'ids': ['p']},
                        {'ids': ['p'], 'vectors': [1., 0.]}):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'cache.npz'
                np.savez_compressed(path, **payload)
                semantic = Mock()
                semantic.index.reconstruct_n.return_value = np.array([[1., 0.]], dtype='float32')
                with patch('src.semantic.vector_search.SemanticVectorSearch', return_value=semantic), \
                        patch.object(search_service, 'get_candidate_ranker', return_value=Mock(lock=Lock())), \
                        patch.object(search_service, 'vector_cache_path', return_value=path):
                    self.assertIs(search_service.load_semantic_search([{'id': 'p'}], 'model', 'hash'), semantic)
                semantic.fit.assert_called_once()
                with np.load(path) as cache:
                    self.assertEqual(cache['vectors'].shape, (1, 2))

    def test_colab_upload_is_verified_and_reconnect_does_not_rewrite_drive(self):
        generator = runpy.run_path(str(api.PROJECT_ROOT / 'scripts/create_colab_bundle.py'))
        digest = hashlib.sha256(b'verified bundle').hexdigest()
        notebook = generator['notebook'](digest)
        upload = next(''.join(cell['source']) for cell in notebook['cells']
                      if 'EXPECTED_SHA256 =' in ''.join(cell['source']))
        prefix = upload.split('extract_root =')[0].replace('from google.colab import files', '')
        for existing, content in [(True, b'verified bundle'), (False, b'verified bundle'),
                                  (False, b'wrong upload')]:
            with self.subTest(existing=existing, content=content), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                drive, runtime = root / 'drive', root / 'runtime'
                drive.mkdir()
                runtime.mkdir()
                name = 'esci_colab_bundle.zip'
                ((drive if existing else runtime) / name).write_bytes(content)
                scope = {'DRIVE_ROOT': drive, 'Path': lambda _: runtime, 'hashlib': hashlib,
                         'shutil': shutil, 'files': Mock(upload=Mock(return_value={name: content}))}
                with patch.object(shutil, 'copy2', wraps=shutil.copy2) as copy:
                    if content == b'wrong upload':
                        with self.assertRaises(AssertionError):
                            exec(prefix, scope)
                        copy.assert_not_called()
                        self.assertFalse((drive / name).exists())
                    else:
                        exec(prefix, scope)
                        source, target = (drive / name, runtime / name) if existing else (runtime / name, drive / name)
                        copy.assert_called_once_with(source, target)
                        self.assertEqual((drive / name).read_bytes(), content)

    def test_numeric_string_stock_and_invalid_values(self):
        for stocks, expected in [(['2', 3], 5), (['nan'], None),
                                 (['bad'], None), ([False], None), (['0'], 0)]:
            with patch.object(dashboard, 'load_products', return_value=[{'stock': x} for x in stocks]):
                self.assertEqual(dashboard.dashboard_data()['totalStock'], expected)

    def test_spelling_cache_does_not_retain_rebuilt_catalogs(self):
        for cls, words in [(CatalogSpelling, ['keyboard']), (FrequencySpelling, Counter(keyboard=8))]:
            spelling = cls(words)
            self.assertEqual(spelling.suggestion('kxyboarx'), ('keyboard', 2))
            reference = weakref.ref(spelling)
            del spelling
            gc.collect()
            self.assertIsNone(reference())

    def test_bounded_candidates_and_nonfuzzy_metadata(self):
        engine = HybridSearch([{'id': str(i), 'title': 'phone'} for i in range(500)])
        result = engine.search('phone', fuzzy=False)
        self.assertEqual(result['searchMode'], 'bm25')
        self.assertEqual(result['candidateCount'], 50)
        self.assertEqual(len(result['results']), 20)
        self.assertNotIn('total', result)

    def test_failed_startup_can_recover_from_request(self):
        engine = Mock()
        engine.search.return_value = {'results': []}
        with patch.object(api._search_ready, 'is_set', return_value=False), \
                patch.object(api, '_search_error', 'Missing catalog'), \
                patch.object(search_service, '_search_engine', None), \
                patch.object(api, 'get_search_engine', return_value=engine) as get:
            self.assertEqual(api.search_products('phone', session={'sub': 'user_test'}), {'results': []})
            get.assert_called_once()

    def test_catalog_cache_checks_manifest_and_refreshes(self):
        database = Mock()
        products = database.__getitem__ = Mock(return_value=Mock())
        rows = products.return_value.find.return_value.sort
        rows.return_value = [{'id': 'p'}]
        manifest = {'sha256': 'first', 'updated_at': '1', 'product_count': 1}
        with patch.object(catalog, 'database', return_value=database), \
                patch.object(catalog, 'version', side_effect=lambda: dict(manifest)), \
                patch.object(catalog, '_products_signature', None), \
                patch.object(catalog, '_products_cache', None):
            first = catalog.load_products()
            self.assertIs(first, catalog.load_products())
            rows.assert_called_once()
            manifest.update(sha256='second')
            self.assertEqual(catalog.load_products(), first)
            self.assertEqual(rows.call_count, 2)
            with patch.object(catalog, 'version', side_effect=catalog.CatalogUpdatingError('importing')):
                with self.assertRaises(catalog.CatalogUpdatingError):
                    catalog.load_products()

    def test_bin_checkpoint_fingerprint_changes_with_weights(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            weights = root / 'pytorch_model.bin'
            weights.write_bytes(b'first')
            first = search_service.vector_cache_path(str(root), 'catalog')
            weights.write_bytes(b'changed weights')
            self.assertNotEqual(first, search_service.vector_cache_path(str(root), 'catalog'))

    def test_corrupt_cache_rebuilt_and_save_failure_is_nonfatal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cache.npz'
            path.write_bytes(b'broken')
            semantic = Mock()
            semantic.index.reconstruct_n.return_value = np.array([[1., 0.]], dtype='float32')
            ranker = Mock(lock=Lock())
            with patch('src.semantic.vector_search.SemanticVectorSearch', return_value=semantic), \
                    patch.object(search_service, 'get_candidate_ranker', return_value=ranker), \
                    patch.object(search_service, 'vector_cache_path', return_value=path), \
                    patch.object(search_service, 'restore_vectors', side_effect=ValueError('truncated')), \
                    patch('numpy.savez_compressed', side_effect=OSError('disk full')):
                self.assertIs(search_service.load_semantic_search([{'id': 'p'}], 'model', 'hash'), semantic)
            semantic.fit.assert_called_once()
            self.assertEqual(list(Path(directory).iterdir()), [path])
            self.assertEqual(path.read_bytes(), b'broken')

    def test_cache_is_atomically_published(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cache.npz'
            semantic = Mock()
            semantic.index.reconstruct_n.return_value = np.array([[1., 0.]], dtype='float32')
            with patch('src.semantic.vector_search.SemanticVectorSearch', return_value=semantic), \
                    patch.object(search_service, 'get_candidate_ranker', return_value=Mock(lock=Lock())), \
                    patch.object(search_service, 'vector_cache_path', return_value=path):
                search_service.load_semantic_search([{'id': 'p'}], 'model', 'hash')
            with np.load(path, allow_pickle=False) as cached:
                self.assertEqual(cached['ids'].tolist(), ['p'])
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_generated_colab_cells_verify_upload_and_invalidate_reports(self):
        generator = runpy.run_path(str(api.PROJECT_ROOT / 'scripts/create_colab_bundle.py'))
        notebook = generator['notebook']('a' * 64)
        code = '\n'.join(''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type'] == 'code')
        self.assertLess(code.index('assert file_hash(runtime_bundle)'),
                        code.index('shutil.copy2(runtime_bundle, drive_bundle)'))
        self.assertLess(code.index('(REPORTS_DIR / name).unlink'), code.index('    run_command(command)'))
        for cell in notebook['cells']:
            if cell['cell_type'] == 'code':
                compile(''.join(cell['source']), '<colab-cell>', 'exec')

    def test_loaded_vectors_forward_model_loading_options(self):
        import faiss
        from src.semantic.vector_search import SemanticVectorSearch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = SemanticVectorSearch('test-model')
            original.products = []
            original.dimension = 2
            original.index = faiss.IndexFlatIP(2)
            original.save(root / 'index.bin', root / 'mapping.pkl')
            restored = SemanticVectorSearch.load(root / 'index.bin', root / 'mapping.pkl',
                                                local_files_only=True, device='cpu')
            self.assertTrue(restored.local_files_only)
            self.assertEqual(restored.requested_device, 'cpu')

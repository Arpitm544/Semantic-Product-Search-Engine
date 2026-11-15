from unittest.mock import MagicMock
import numpy as np
import pytest
from src.semantic.atlas_search import AtlasVectorSearch, index_definition


def engine(ready=True):
    db = MagicMock()
    db.__getitem__.return_value.find_one.return_value = {
        'status': 'ready' if ready else 'building', 'product_count': 1}
    db.__getitem__.return_value.list_search_indexes.return_value = [
        {'queryable': True, 'latestDefinition': index_definition(2)}]
    encoder = MagicMock()
    encoder.get_sentence_embedding_dimension.return_value = 2
    encoder.encode.return_value = np.array([[1., 0.]])
    return db, encoder


def test_atlas_query_uses_cloud_vectors_and_returns_catalog_records():
    db, encoder = engine()
    product = {'id': 'esci:1', 'title': 'Headphones'}
    semantic = AtlasVectorSearch(db, [product], encoder, 'model', 'generation')
    semantic.collection.aggregate.return_value = [
        {'id': 'esci:1', 'score': .9}, {'id': 'stale', 'score': .8}]
    assert semantic.search('headphones', 5) == [(product, .9)]
    stage = semantic.collection.aggregate.call_args.args[0][0]['$vectorSearch']
    assert stage['queryVector'] == [1., 0.]
    assert stage['limit'] == 1
    assert stage['path'] == 'embedding'
    assert semantic.search('x', 0) == []


def test_incomplete_upload_cannot_serve():
    db, encoder = engine(ready=False)
    with pytest.raises(RuntimeError, match='missing or outdated'):
        AtlasVectorSearch(db, [{'id': 'esci:1'}], encoder, 'model', 'generation')


def test_wrong_index_dimensions_cannot_serve():
    db, encoder = engine()
    encoder.get_sentence_embedding_dimension.return_value = 3
    with pytest.raises(RuntimeError, match='different definition'):
        AtlasVectorSearch(db, [{'id': 'esci:1'}], encoder, 'model', 'generation')


def test_api_loads_atlas_and_propagates_setup_errors(monkeypatch):
    from api import search_service
    from src.data import catalog
    from src.semantic import atlas_search, identity
    db = MagicMock()
    ranker = MagicMock()
    monkeypatch.setattr(catalog, 'database', lambda: db)
    monkeypatch.setattr(search_service, 'get_candidate_ranker', lambda: ranker)
    monkeypatch.setattr(identity, 'vector_generation', lambda *args: 'generation')
    constructor = MagicMock()
    monkeypatch.setattr(atlas_search, 'AtlasVectorSearch', constructor)
    products = [{'id': 'esci:1'}]
    assert search_service.load_semantic_search(products, 'model', 'hash') is constructor.return_value
    assert constructor.call_args.args[0] is db
    assert constructor.call_args.args[2] is ranker.encoder
    assert constructor.call_args.args[-1] == 'generation'
    assert constructor.call_args.kwargs['model_lock'] is ranker.lock
    constructor.side_effect = RuntimeError('Index not ready')
    with pytest.raises(RuntimeError, match='Index not ready'):
        search_service.load_semantic_search(products, 'model', 'hash')


def test_encoding_holds_the_model_lock_but_the_atlas_query_does_not():
    from threading import Lock
    db, encoder = engine()
    lock = Lock()
    product = {'id': 'esci:1', 'title': 'Headphones'}
    semantic = AtlasVectorSearch(db, [product], encoder, 'model', 'generation', model_lock=lock)
    held = {}

    def encode(*args, **kwargs):
        held['encode'] = lock.locked()
        return np.array([[1., 0.]])

    def aggregate(*args, **kwargs):
        held['atlas'] = lock.locked()
        return [{'id': 'esci:1', 'score': .9}]

    encoder.encode.side_effect = encode
    semantic.collection.aggregate.side_effect = aggregate
    assert semantic.search('headphones', 5) == [(product, .9)]
    assert held == {'encode': True, 'atlas': False}


def test_slow_atlas_query_does_not_block_other_model_users():
    """A search waiting on Atlas must not stall Shopping ranking or other searches."""
    from threading import Event, Lock, Thread
    from src.search.product_search import ProductSearch
    db, encoder = engine()
    lock = Lock()
    product = {'id': 'esci:1', 'title': 'Headphones', 'representation_text': 'headphones'}
    semantic = AtlasVectorSearch(db, [product], encoder, 'model', 'generation', model_lock=lock)
    in_atlas, release = Event(), Event()

    def slow_aggregate(*args, **kwargs):
        in_atlas.set()
        assert release.wait(5)
        return [{'id': 'esci:1', 'score': .9}]

    semantic.collection.aggregate.side_effect = slow_aggregate
    reranker = MagicMock()
    reranker.predict.side_effect = lambda pairs, **kwargs: [1.0] * len(pairs)
    search = ProductSearch([product], semantic, reranker, model_lock=lock)
    results = []
    worker = Thread(target=lambda: results.append(search.search('headphones', fuzzy=False)))
    worker.start()
    try:
        assert in_atlas.wait(5)
        # Another request (e.g. Shopping ranking) can use the models meanwhile.
        assert lock.acquire(timeout=1)
        lock.release()
    finally:
        release.set()
        worker.join(5)
    assert results and results[0]['results'][0]['id'] == 'esci:1'


def test_reranking_and_unmanaged_semantic_search_stay_serialized():
    from threading import Lock
    from src.search.product_search import ProductSearch
    lock = Lock()
    product = {'id': 'p', 'title': 'Headphones', 'representation_text': 'headphones'}
    held = {}
    semantic = MagicMock(model_name='local')
    semantic.manages_model_lock = MagicMock()  # not literally True

    def local_search(query, top_k):
        held['semantic'] = lock.locked()
        return [(product, 1.0)]

    def predict(pairs, **kwargs):
        held['reranker'] = lock.locked()
        return [1.0] * len(pairs)

    semantic.search.side_effect = local_search
    reranker = MagicMock()
    reranker.predict.side_effect = predict
    assert ProductSearch([product], semantic, reranker, model_lock=lock).search('headphones', fuzzy=False)['results']
    assert held == {'semantic': True, 'reranker': True}
    assert not lock.locked()

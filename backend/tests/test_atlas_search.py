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
    constructor.side_effect = RuntimeError('Index not ready')
    with pytest.raises(RuntimeError, match='Index not ready'):
        search_service.load_semantic_search(products, 'model', 'hash')

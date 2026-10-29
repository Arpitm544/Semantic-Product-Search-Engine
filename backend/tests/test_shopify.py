"""Offline Shopify contracts; no store credentials or model downloads."""
import base64
import hashlib
import hmac
from types import SimpleNamespace
from unittest.mock import MagicMock
import numpy as np
import pytest
from src.integrations.shopify.mapper import map_product
from src.integrations.shopify.webhooks import verify
from src.integrations.shopify.config import Settings
from src.integrations.shopify import sync
from src.search.shopify_index import SemanticIndex


def product(**kwargs):
    return {'id': 'gid://shopify/Product/1', 'title': 'Running shoes', 'description': 'Blue',
            'status': 'ACTIVE', 'options': [], **kwargs}


def test_mapping_hash_ignores_selling_metadata_and_bounds_text():
    a = map_product(product(description='x' * 10000), 'test.myshopify.com')
    b = map_product(product(description='x' * 10000, updatedAt='tomorrow', price=99), 'test.myshopify.com')
    assert a['text_hash'] == b['text_hash']
    assert len(a['description']) == 6000
    assert a['id'] != map_product(product(), 'other.myshopify.com')['id']
    assert a['text_hash'] != map_product(product(title='Hiking boots'), 'test.myshopify.com')['text_hash']


def test_signature_uses_exact_raw_bytes():
    body = b'{"id":1}'
    signature = base64.b64encode(hmac.new(b'secret', body, hashlib.sha256).digest()).decode()
    assert verify(body, signature, 'secret')
    assert not verify(body + b' ', signature, 'secret')
    assert not verify(body, signature, '')


def test_settings_prevent_arbitrary_hosts(monkeypatch):
    monkeypatch.setenv('SHOPIFY_ENABLED', 'true')
    with pytest.raises(ValueError):
        Settings(shop='localhost', admin_token='a', storefront_token='b', collection='c').validate()


def test_capped_or_missing_collection_never_deletes(monkeypatch):
    repository = MagicMock()
    client = MagicMock()
    monkeypatch.setattr(sync, 'Client', lambda _: client)
    settings = SimpleNamespace(shop='test.myshopify.com', collection='collection', cap=1)
    client.query.return_value = {'collection': {'products': {'nodes': [product()],
                                          'pageInfo': {'hasNextPage': True, 'endCursor': 'next'}}}}
    with pytest.raises(ValueError, match='cap'):
        sync.synchronize(settings, repository, None)
    repository.products.delete_many.assert_not_called()
    repository.products.replace_one.assert_not_called()
    client.query.return_value = {'collection': None}
    with pytest.raises(ValueError, match='unavailable'):
        sync.synchronize(settings, repository, None)
    repository.products.delete_many.assert_not_called()


def test_cosine_index_preserves_product_mapping():
    encoder = SimpleNamespace(encode=lambda *args, **kw: np.array([[0., 1.]]))
    index = SemanticIndex([{'id': 'a'}, {'id': 'b'}], np.array([[1., 0.], [0., 1.]]), encoder)
    assert index.search('blue shoes', 1)[0][0]['id'] == 'b'
    with pytest.raises(ValueError):
        SemanticIndex([{'id': 'a'}], np.array([[np.nan]]), encoder)


def test_hydration_caches_null_and_expires(monkeypatch):
    from src.integrations.shopify import hydration
    hydration.invalidate('test.myshopify.com')
    client = MagicMock(settings=SimpleNamespace(shop='test.myshopify.com', ttl=60))
    client.query.return_value = {'nodes': [None]}
    assert hydration.hydrate(client, ['p']) == {'p': None}
    hydration.hydrate(client, ['p'])
    assert client.query.call_count == 1
    hydration.invalidate('test.myshopify.com')
    hydration.hydrate(client, ['p'])
    assert client.query.call_count == 2


def test_embeddings_reused_without_changing_published_pointer(tmp_path, monkeypatch):
    from src.search import shopify_index
    monkeypatch.setattr(shopify_index, 'root', lambda _: tmp_path)
    monkeypatch.setattr(shopify_index, 'vector_generation', lambda *args: 'model-v1')
    from threading import Lock
    encoder = MagicMock()
    encoder.encode.return_value = np.array([[1., 0.]])
    ranker = SimpleNamespace(encoder=encoder, lock=Lock())
    record = map_product(product(), 'test.myshopify.com')
    first = shopify_index.build([record], 'test.myshopify.com', ranker)
    second = shopify_index.build([record], 'test.myshopify.com', ranker)
    assert encoder.encode.call_count == 1
    assert first['generation'] != second['generation']
    assert not (tmp_path / 'current.json').exists()


def test_failed_index_build_preserves_products_and_pointer(monkeypatch):
    repository = MagicMock()
    client = MagicMock()
    monkeypatch.setattr(sync, 'Client', lambda _: client)
    settings = SimpleNamespace(shop='test.myshopify.com', collection='c', cap=5)
    client.query.side_effect = [
        {'collection': {'products': {'nodes': [product()], 'pageInfo': {'hasNextPage': False}}}},
        {'nodes': [{'id': product()['id'], 'onlineStoreUrl': 'https://test.example/products/shoes'}]},
    ]
    monkeypatch.setattr(sync, 'build', MagicMock(side_effect=RuntimeError('bad model')))
    pointer = MagicMock()
    monkeypatch.setattr(sync, 'atomic_json', pointer)
    with pytest.raises(RuntimeError, match='bad model'):
        sync.synchronize(settings, repository, None)
    repository.products.replace_one.assert_not_called()
    repository.products.delete_many.assert_not_called()
    pointer.assert_not_called()


def test_webhook_ingress_durability_and_authentication(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api import shopify_routes
    from pymongo.errors import ConnectionFailure
    repository = MagicMock()
    settings = SimpleNamespace(shop='test.myshopify.com', secret='secret')
    monkeypatch.setattr(shopify_routes, 'context', lambda: (settings, repository))
    app = FastAPI()
    app.include_router(shopify_routes.router)
    body = b'{"id":1}'
    signature = base64.b64encode(hmac.new(b'secret', body, hashlib.sha256).digest()).decode()
    headers = {'x-shopify-shop-domain': settings.shop, 'x-shopify-hmac-sha256': signature,
               'x-shopify-webhook-id': 'delivery-1', 'x-shopify-topic': 'products/update'}
    client = TestClient(app)
    assert client.post('/api/shopify/webhooks', content=body, headers=headers).status_code == 200
    repository.enqueue.assert_called_once_with('delivery-1')
    assert client.post('/api/shopify/webhooks', content=body + b' ', headers=headers).status_code == 401
    repository.jobs.assert_not_called()
    repository.enqueue.side_effect = ConnectionFailure('offline')
    assert client.post('/api/shopify/webhooks', content=body, headers=headers).status_code == 503


def test_successful_sync_publishes_after_product_writes(monkeypatch, tmp_path):
    repository = MagicMock()
    settings = SimpleNamespace(shop='test.myshopify.com', collection='c', cap=5)
    client = MagicMock()
    client.query.side_effect = [
        {'collection': {'products': {'nodes': [product()], 'pageInfo': {'hasNextPage': False}}}},
        {'nodes': [{'id': product()['id'], 'onlineStoreUrl': 'https://test.example/products/shoes'}]},
    ]
    monkeypatch.setattr(sync, 'Client', lambda _: client)
    monkeypatch.setattr(sync, 'build', lambda *args: {'generation': 'abc', 'count': 1})
    monkeypatch.setattr(sync, 'root', lambda _: tmp_path)
    def publish(path, manifest):
        repository.products.replace_one.assert_called_once()
        repository.products.delete_many.assert_called_once()
        assert manifest['generation'] == 'abc'
    monkeypatch.setattr(sync, 'atomic_json', publish)
    assert sync.synchronize(settings, repository, None) == 1
    record = repository.products.replace_one.call_args.args[1]
    assert record['eligible'] is True
    assert record['shop_domain'] == settings.shop

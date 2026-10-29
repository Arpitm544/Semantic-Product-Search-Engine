"""Wishlist ownership and validation at the HTTP boundary."""
from datetime import datetime, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from pymongo.errors import ConnectionFailure
from api.main import app
from api.auth import require_session
from api.saved_products import saved_id

@pytest.fixture
def client():
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[require_session] = lambda: {"sub": "user_alice"}
    yield TestClient(app)
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)

BODY = {"source": "mongo", "identity": "product-1", "product": {"title": "Headphones", "price": 100}}

def test_save_is_owned_and_idempotent(client):
    with patch('api.saved_products.collection') as factory:
        first = client.put('/api/saved-products', json=BODY)
        second = client.put('/api/saved-products', json=BODY)
        assert first.status_code == 200
        assert first.json() == second.json()
        query, update = factory.return_value.update_one.call_args.args
        assert query == {"_id": saved_id('user_alice', 'mongo', 'product-1'), "user_id": "user_alice"}
        assert update['$setOnInsert']['user_id'] == 'user_alice'
        assert factory.return_value.update_one.call_args.kwargs['upsert'] is True
        assert saved_id('user_bob', 'mongo', 'product-1') != query['_id']
        assert saved_id('user_alice', 'serpapi', 'product-1') != query['_id']

def test_cannot_supply_another_owner(client):
    assert client.put('/api/saved-products', json={**BODY, 'user_id': 'user_bob'}).status_code == 422

def test_remove_always_scopes_owner(client):
    with patch('api.saved_products.collection') as factory:
        assert client.delete('/api/saved-products/bobs-item').status_code == 200
        factory.return_value.delete_one.assert_called_once_with({'_id': 'bobs-item', 'user_id': 'user_alice'})

def test_list_scopes_owner_and_hides_internal_fields(client):
    with patch('api.saved_products.collection') as factory:
        factory.return_value.find.return_value.sort.return_value.skip.return_value.limit.return_value = [{
            '_id': 'item', 'user_id': 'user_alice', 'source': 'mongo', 'identity': '1',
            'saved_at': datetime.now(timezone.utc), 'product': {'title': 'Headphones'},
        }]
        response = client.get('/api/saved-products')
        assert response.status_code == 200
        factory.return_value.find.assert_called_once_with({'user_id': 'user_alice'})
        assert 'user_id' not in response.json()['items'][0]
        assert response.json()['hasMore'] is False

def test_status_scopes_owner(client):
    with patch('api.saved_products.collection') as factory:
        factory.return_value.find_one.return_value = None
        response = client.get('/api/saved-products/status?source=mongo&identity=product-1')
        assert response.json()['saved'] is False
        assert factory.return_value.find_one.call_args.args[0]['user_id'] == 'user_alice'

@pytest.mark.parametrize('product', [{'title': ''}, {'title': 'x', 'url': 'javascript:alert(1)'}, {'title': 'x' * 501}])
def test_reject_invalid_snapshot(client, product):
    assert client.put('/api/saved-products', json={**BODY, 'product': product}).status_code == 422

def test_database_failure_is_safe_and_retryable(client):
    with patch('api.saved_products.collection', side_effect=ConnectionFailure('private database details')):
        response = client.get('/api/saved-products')
        assert response.status_code == 503
        assert 'private database details' not in response.text

@pytest.mark.parametrize('method,path', [('get','/api/saved-products'), ('put','/api/saved-products'),
                                         ('delete','/api/saved-products/item'),
                                         ('get','/api/saved-products/status?source=mongo&identity=1')])
def test_all_routes_require_authentication(method, path):
    response = getattr(TestClient(app), method)(path, **({'json': BODY} if method == 'put' else {}))
    assert response.status_code == 401

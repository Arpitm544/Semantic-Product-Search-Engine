"""Account-feature validation, ownership, and snapshot regressions."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from pymongo.errors import ConnectionFailure

from api.main import app
from api.auth import require_session
from api import account_features as features, account_store, price_alerts, saved_products
from api.product_prices import price_info, apply_preferences

ID = 'a' * 64
OTHER = 'b' * 64
COL = 'c' * 32
TIME = datetime.now(timezone.utc)


@pytest.fixture
def mockdb():
    collections = {name: MagicMock() for name in ['product_collections', 'user_preferences', 'saved_comparisons', 'price_alerts', 'price_notifications']}
    for value in collections.values():
        value.find_one.return_value = None
        value.count_documents.return_value = 0
    lookup = lambda name: collections[name]
    with patch.object(features, 'store', side_effect=lookup), patch.object(account_store, 'store', side_effect=lookup), \
            patch.object(price_alerts, 'store', side_effect=lookup), patch.object(saved_products, 'collection') as saved:
        saved.return_value.find.return_value = []
        yield collections, saved.return_value


@pytest.fixture
def client(mockdb):
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[require_session] = lambda: {'sub': 'alice'}
    yield TestClient(app)
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def saved_row(identifier=ID):
    return {'_id': identifier, 'user_id': 'alice', 'source': 'mongo', 'identity': 'catalog-1',
            'product': {'title': 'Headphones', 'price': 100, 'currency': 'USD', 'rating': 4.5, 'attributes': ['Wireless']}, 'saved_at': TIME}


def test_create_collection_uses_session_and_trims_name(client, mockdb):
    db, _ = mockdb
    response = client.post('/api/collections', json={'name': '  College essentials  '})
    assert response.status_code == 201
    row = db['product_collections'].insert_one.call_args.args[0]
    assert row['name'] == 'College essentials' and row['user_id'] == 'alice'
    assert row['product_ids'] == [] and len(row['_id']) == 32
    assert 'user_id' not in response.json()


@pytest.mark.parametrize('body', [{'name': ' '}, {'name': 'x' * 101}, {'name': 'X', 'user_id': 'bob'}])
def test_invalid_collection_input(client, body):
    assert client.post('/api/collections', json=body).status_code == 422


def test_foreign_collection_is_not_available(client, mockdb):
    db, _ = mockdb
    assert client.get('/api/collections/' + COL).status_code == 404
    assert client.patch('/api/collections/' + COL, json={'name': 'X'}).status_code == 404
    assert client.put(f'/api/collections/{COL}/products/{ID}').status_code == 404
    for call in db['product_collections'].find_one.call_args_list:
        assert call.args[0] == {'_id': COL, 'user_id': 'alice'}
    db['product_collections'].update_one.assert_not_called()


def test_collection_product_add_is_owned_and_bounded(client, mockdb):
    db, saved = mockdb
    db['product_collections'].find_one.return_value = {'_id': COL, 'user_id': 'alice', 'product_ids': [], 'name': 'Work', 'updated_at': TIME}
    assert client.put(f'/api/collections/{COL}/products/{ID}').status_code == 404
    saved.find.return_value = [saved_row()]
    db['product_collections'].update_one.return_value.matched_count = 0
    assert client.put(f'/api/collections/{COL}/products/{ID}').status_code == 409
    db['product_collections'].update_one.return_value.matched_count = 1
    assert client.put(f'/api/collections/{COL}/products/{ID}').status_code == 200
    query, update = db['product_collections'].update_one.call_args.args
    assert query['user_id'] == 'alice' and '$expr' in query
    assert update['$addToSet'] == {'product_ids': ID}
    assert saved.find.call_args.args[0]['user_id'] == 'alice'


def test_collection_detail_filters_by_owner(client, mockdb):
    db, saved = mockdb
    db['product_collections'].find_one.return_value = {'_id': COL, 'user_id': 'alice', 'name': 'Work', 'product_ids': [ID], 'updated_at': TIME}
    saved.find.return_value = [saved_row()]
    body = client.get('/api/collections/' + COL).json()
    assert body['items'][0]['product']['title'] == 'Headphones'
    saved.find.assert_called_with({'user_id': 'alice', '_id': {'$in': [ID]}})


def test_deletions_never_cross_owners(client, mockdb):
    db, _ = mockdb
    client.delete('/api/collections/' + COL)
    db['product_collections'].delete_one.assert_called_with({'_id': COL, 'user_id': 'alice'})
    client.delete(f'/api/collections/{COL}/products/{ID}')
    assert db['product_collections'].update_one.call_args.args[0]['user_id'] == 'alice'
    client.delete('/api/comparisons/' + COL)
    db['saved_comparisons'].delete_one.assert_called_with({'_id': COL, 'user_id': 'alice'})


def test_preferences_defaults_save_and_reset_are_private(client, mockdb):
    db, _ = mockdb
    defaults = client.get('/api/preferences').json()
    assert defaults['defaultSource'] == 'mongo' and defaults['applyByDefault'] is False
    response = client.put('/api/preferences', json={**defaults, 'minBudget': 10, 'maxBudget': 50, 'brands': ['Sony', 'Sony']})
    assert response.status_code == 200 and response.json()['brands'] == ['Sony']
    assert db['user_preferences'].update_one.call_args.args[0] == {'_id': 'alice', 'user_id': 'alice'}
    assert client.delete('/api/preferences').status_code == 200
    db['user_preferences'].delete_one.assert_called_with({'_id': 'alice', 'user_id': 'alice'})


@pytest.mark.parametrize('body', [{'minBudget': 50, 'maxBudget': 10}, {'currency': 'XXX'}, {'brands': ['x'] * 21}, {'user_id': 'bob'}, {'minBudget': -1}])
def test_preferences_validate_inputs(client, body):
    assert client.put('/api/preferences', json=body).status_code == 422


def test_comparison_snapshot_requires_two_to_four_owned_products(client, mockdb):
    db, saved = mockdb
    assert client.post('/api/comparisons', json={'name': 'Audio', 'savedIds': [ID, OTHER]}).status_code == 404
    saved.find.return_value = [saved_row(), saved_row(OTHER)]
    response = client.post('/api/comparisons', json={'name': 'Audio', 'savedIds': [ID, OTHER]})
    assert response.status_code == 201
    snapshot = db['saved_comparisons'].insert_one.call_args.args[0]
    assert snapshot['user_id'] == 'alice'
    assert snapshot['products'][0]['product']['rating'] == 4.5
    assert snapshot['products'][0]['product']['attributes'] == ['Wireless']
    assert 'user_id' not in response.json()
    for ids in [[ID], [ID, ID], [ID] * 5]:
        assert client.post('/api/comparisons', json={'name': 'Audio', 'savedIds': ids}).status_code == 422


def test_safe_database_failure(client, mockdb):
    db, _ = mockdb
    db['product_collections'].find.side_effect = ConnectionFailure('private host details')
    response = client.get('/api/collections')
    assert response.status_code == 503 and 'private host' not in response.text


def test_remove_saved_product_cleans_membership_and_pauses_alerts(mockdb):
    db, _ = mockdb
    account_store.clean_saved_links('alice', ID)
    assert db['product_collections'].update_many.call_args.args[0] == {'user_id': 'alice', 'product_ids': ID}
    query, update = db['price_alerts'].update_many.call_args.args
    assert query == {'user_id': 'alice', 'saved_id': ID} and update['$set']['enabled'] is False
    db['saved_comparisons'].delete_many.assert_not_called()


@pytest.mark.parametrize('product,currency', [({'price': 20, 'priceLabel': '₹20'}, 'INR'), ({'price': 20, 'currency': 'USD'}, 'USD'), ({'price': 20, 'priceLabel': '$20'}, None), ({'price': True, 'currency': 'USD'}, None), ({'price': -1, 'currency': 'USD'}, None), ({'price': 'NaN', 'currency': 'USD'}, None)])
def test_price_identity_does_not_guess_ambiguous_currency(product, currency):
    result = price_info(product)
    assert (result['currency'] if result else None) == currency


def test_preference_filters_currency_stock_and_exact_brand():
    preferences = features.Preferences(currency='USD', minBudget=10, maxBudget=50, brands=['Sony'], categories=['Audio'], inStockOnly=True).model_dump()
    base = {'title': 'Headphones', 'price': 20, 'currency': 'USD', 'brand': 'SONY', 'category': 'audio', 'stock': 1}
    products = [base, {**base, 'price': None}, {**base, 'currency': 'INR'}, {**base, 'stock': 0}, {**base, 'brand': 'Sony-like'}]
    result = apply_preferences({'results': products}, preferences)
    assert result['results'] == [base] and result['preferencesApplied'] is True
    assert 'unavailable' in result['warning']


@pytest.mark.parametrize('method,path,body', [
    ('get','/api/collections',None), ('post','/api/collections',{'name':'X'}), ('get',f'/api/collections/{COL}',None),
    ('patch',f'/api/collections/{COL}',{'name':'X'}), ('delete',f'/api/collections/{COL}',None),
    ('put',f'/api/collections/{COL}/products/{ID}',None), ('delete',f'/api/collections/{COL}/products/{ID}',None),
    ('get','/api/preferences',None), ('put','/api/preferences',{}), ('delete','/api/preferences',None),
    ('get','/api/comparisons',None), ('post','/api/comparisons',{'name':'X','savedIds':[ID,OTHER]}),
    ('patch',f'/api/comparisons/{COL}',{'name':'X'}), ('delete',f'/api/comparisons/{COL}',None),
    ('get','/api/account-overview',None), ('get','/api/price-alerts',None), ('put','/api/price-alerts',{'savedId':ID}),
    ('get',f'/api/price-alerts/eligibility/{ID}',None), ('patch',f'/api/price-alerts/{ID}',{'enabled':True}),
    ('delete',f'/api/price-alerts/{ID}',None), ('post',f'/api/price-alerts/{ID}/check',None),
    ('get','/api/notifications',None), ('patch',f'/api/notifications/{ID}/read',None),
])
def test_all_new_account_endpoints_require_authentication(method, path, body):
    response = getattr(TestClient(app), method)(path, **({'json': body} if body is not None else {}))
    assert response.status_code == 401


@pytest.mark.parametrize('minimum,maximum,expected', [
    (None, None, [5, 10, 20, 30]), (10, None, [10, 20, 30]),
    (None, 20, [5, 10, 20]), (10, 20, [10, 20]), (0, 0, []),
])
def test_preference_budget_bounds_remain_inclusive(minimum, maximum, expected):
    preferences = features.Preferences(currency='USD', minBudget=minimum, maxBudget=maximum).model_dump()
    products = [{'title': 'Product', 'price': amount, 'currency': 'USD'} for amount in [5, 10, 20, 30]]
    result = apply_preferences({'results': products, 'warning': 'Provider notice.'}, preferences)
    assert [product['price'] for product in result['results']] == expected
    assert result['warning'].startswith('Provider notice.')

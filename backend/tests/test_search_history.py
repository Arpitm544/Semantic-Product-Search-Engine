"""Personal dashboard privacy and successful-search recording regressions."""
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from pymongo.errors import ConnectionFailure
import pytest

from api.main import app
from api.auth import require_session
from api import search_history as history


@pytest.fixture
def client():
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[require_session] = lambda: {"sub": "alice", "sid": "sess_alice"}
    yield TestClient(app)
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def document(**overrides):
    return {"_id": "entry", "user_id": "alice", "query": "headphones", "source": "mongo", "fuzzy": False,
            "result_count": 3, "searched_at": datetime(2026, 10, 29), **overrides}


def test_remember_deduplicates_per_user_query_source_and_spelling():
    with patch.object(history, 'collection') as factory:
        for _ in range(2):
            result = history.remember_search('alice', history.SearchContext('headphones', 'mongo', False), {'results': []})
            assert result['historySaved'] is True
        calls = factory.return_value.update_one.call_args_list
        assert calls[0].args[0] == calls[1].args[0]
        owner = calls[0].args[0]
        assert owner['user_id'] == 'alice'
        data = calls[0].args[1]['$set']
        assert data['query'] == 'headphones' and data['fuzzy'] is False and data['result_count'] == 0
        assert data['searched_at'].tzinfo == timezone.utc
        for user, source, fuzzy in [('bob', 'mongo', False), ('alice', 'serpapi', False), ('alice', 'mongo', True)]:
            history.remember_search(user, history.SearchContext('headphones', source, fuzzy), {'results': []})
            assert factory.return_value.update_one.call_args.args[0]['_id'] != owner['_id']


def test_failed_history_write_keeps_results():
    payload = {'results': [{'title': 'Headphones'}], 'warning': 'Existing ranking notice'}
    with patch.object(history, 'collection', side_effect=ConnectionFailure('private uri')):
        result = history.remember_search('alice', history.SearchContext('headphones'), payload)
    assert result['results'] == payload['results'] and result['warning'] == payload['warning']
    assert result['historySaved'] is False and 'historySaved' not in payload


def test_blank_query_is_not_recorded():
    with patch.object(history, 'collection') as factory:
        assert history.remember_search('alice', history.SearchContext(''), {'results': []}) == {'results': []}
        factory.assert_not_called()


def test_history_is_scoped_paginated_and_serializes_utc(client):
    with patch.object(history, 'collection') as factory:
        factory.return_value.find.return_value.sort.return_value.skip.return_value.limit.return_value = [document(), document(_id='next')]
        response = client.get('/api/search-history?limit=1&offset=2')
        assert response.status_code == 200
        factory.return_value.find.assert_called_once_with({'user_id': 'alice'})
        factory.return_value.find.return_value.sort.return_value.skip.assert_called_once_with(2)
        factory.return_value.find.return_value.sort.return_value.skip.return_value.limit.assert_called_once_with(2)
        body = response.json()
        assert body['hasMore'] is True and len(body['items']) == 1
        assert body['items'][0]['searchedAt'].endswith('+00:00')
        assert 'user_id' not in body['items'][0] and body['items'][0]['fuzzy'] is False


def test_deletes_are_owner_scoped(client):
    with patch.object(history, 'collection') as factory:
        assert client.delete('/api/search-history/bobs-id').status_code == 200
        factory.return_value.delete_one.assert_called_once_with({'_id': 'bobs-id', 'user_id': 'alice'})
        assert client.delete('/api/search-history').status_code == 200
        factory.return_value.delete_many.assert_called_once_with({'user_id': 'alice'})


def test_dashboard_scopes_saved_and_history_counts_and_previews(client):
    with patch.object(history, 'collection') as histories, patch.object(history.saved_products, 'collection') as saved:
        histories.return_value.find.return_value.sort.return_value.skip.return_value.limit.return_value = [document()]
        histories.return_value.count_documents.return_value = 7
        saved.return_value.count_documents.return_value = 2
        saved.return_value.find.return_value.sort.return_value.limit.return_value = [{
            '_id': 'saved-id', 'user_id': 'alice', 'source': 'mongo', 'identity': '1',
            'product': {'title': 'Headphones'}, 'saved_at': datetime.now(timezone.utc),
        }]
        response = client.get('/api/personal-dashboard')
        assert response.status_code == 200
        body = response.json()
        assert body['searchCount'] == 7 and body['savedCount'] == 2
        assert len(body['savedProducts']) == 1 and len(body['recentSearches']) == 1
        histories.return_value.count_documents.assert_called_once_with({'user_id': 'alice'})
        saved.return_value.count_documents.assert_called_once_with({'user_id': 'alice'})
        saved.return_value.find.assert_called_once_with({'user_id': 'alice'})
        assert 'user_id' not in body['savedProducts'][0]


@pytest.mark.parametrize('path', ['/api/search-history', '/api/personal-dashboard'])
def test_database_errors_are_safe(client, path):
    with patch.object(history, 'collection', side_effect=ConnectionFailure('private uri')):
        response = client.get(path)
        assert response.status_code == 503 and 'private uri' not in response.text


@pytest.mark.parametrize('method,path', [('get', '/api/search-history'), ('delete', '/api/search-history'),
                                         ('delete', '/api/search-history/entry'), ('get', '/api/personal-dashboard')])
def test_routes_require_authentication(method, path):
    assert getattr(TestClient(app), method)(path).status_code == 401


@pytest.mark.parametrize('params', ['limit=0', 'limit=51', 'offset=-1', 'offset=100001'])
def test_pagination_is_bounded(client, params):
    assert client.get('/api/search-history?' + params).status_code == 422


def test_success_records_original_query_and_trusted_identity(client):
    engine = Mock()
    engine.search.return_value = {'results': [], 'correctedQuery': 'headphones'}
    with patch('api.main.get_search_engine', return_value=engine), patch('api.main._search_ready.is_set', return_value=True), \
            patch('api.main.remember_search', side_effect=lambda *args: args[-1]) as record:
        assert client.get('/api/search?q=hedphones&fuzzy=0').status_code == 200
        record.assert_called_once_with('alice', history.SearchContext('hedphones', 'mongo', False), engine.search.return_value)


def test_shopping_success_is_recorded(client):
    with patch('api.main.search_shopping', return_value={'results': []}), \
            patch('api.main.rank_shopping_response', return_value={'results': []}), \
            patch('api.main.remember_search', side_effect=lambda *args: args[-1]) as record:
        assert client.get('/api/search?q=headphones&source=serpapi').status_code == 200
        record.assert_called_once_with('alice', history.SearchContext('headphones', 'serpapi'), {'results': []})


def test_invalid_and_failed_searches_are_not_recorded(client):
    with patch('api.main.remember_search') as record:
        assert client.get('/api/search?q=x&source=unknown').status_code == 400
        assert client.get('/api/search?q=' + 'x' * 513).status_code == 400
        with patch('api.main.get_search_engine', side_effect=OSError('unavailable')), \
                patch('api.main._search_ready.is_set', return_value=True):
            assert client.get('/api/search?q=headphones').status_code == 503
        record.assert_not_called()


@pytest.mark.parametrize('source', ['mongo', 'serpapi'])
def test_preference_search_records_filtered_count_and_original_options(client, source):
    from api.account_features import Preferences
    products = [{'title': 'In budget', 'price': 20, 'currency': 'USD'},
                {'title': 'Over budget', 'price': 100, 'currency': 'USD'}]
    engine = Mock()
    engine.search.return_value = {'results': products}
    preferences = Preferences(currency='USD', maxBudget=50).model_dump()
    with patch('api.main.get_search_engine', return_value=engine), \
            patch('api.main._search_ready.is_set', return_value=True), \
            patch('api.main.search_shopping', return_value={'results': products}), \
            patch('api.main.rank_shopping_response', side_effect=lambda payload: payload), \
            patch('api.main.load_preferences', return_value=preferences) as load, \
            patch.object(history, 'collection') as factory:
        response = client.get('/api/search', params={
            'q': '  headphones  ', 'source': source, 'fuzzy': '0', 'preferences': '1',
        })
        assert response.status_code == 200
        assert response.json()['results'] == products[:1]
        load.assert_called_once_with('alice')
        data = factory.return_value.update_one.call_args.args[1]['$set']
        assert data['query'] == 'headphones'
        assert data['source'] == source and data['fuzzy'] is False
        assert data['use_preferences'] is True and data['result_count'] == 1
        preference_key = factory.return_value.update_one.call_args.args[0]['_id']
        history.remember_search('alice', history.SearchContext('headphones', source, False), {'results': products})
        assert factory.return_value.update_one.call_args.args[0]['_id'] != preference_key

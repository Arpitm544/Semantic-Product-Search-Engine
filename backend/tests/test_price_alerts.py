"""Price checking rejects mismatched offers, currencies, and duplicate deliveries."""
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import ConnectionFailure

from api import price_alerts as alerts
from api.auth import require_session
from api.main import app
from api.account_store import now
from tests.test_account_features import mockdb, saved_row, ID, OTHER


def alert_row(**overrides):
    return {'_id': ID, 'user_id': 'alice', 'saved_id': ID, 'product': {'title': 'Headphones', 'merchant': 'Store'},
            'source': 'mongo', 'identity': 'catalog-1', 'currency': 'USD', 'baseline_price': 100,
            'min_price': 100, 'target_price': 90, 'enabled': True, 'revision': 'version1',
            'market': alerts.market_settings(), 'next_check_at': now() - timedelta(seconds=1),
            'updated_at': now(), **overrides}


@pytest.fixture
def client(mockdb):
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[require_session] = lambda: {'sub': 'alice'}
    yield TestClient(app)
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def test_alert_creation_validates_baseline_target_and_ownership(client, mockdb):
    db, saved = mockdb
    assert client.put('/api/price-alerts', json={'savedId': ID}).status_code == 404
    saved.find.return_value = [saved_row()]
    assert client.put('/api/price-alerts', json={'savedId': ID, 'targetPrice': 101}).status_code == 422
    db['price_alerts'].find_one.side_effect = [None, alert_row()]
    response = client.put('/api/price-alerts', json={'savedId': ID, 'targetPrice': 90})
    assert response.status_code == 200
    query, fields = db['price_alerts'].update_one.call_args.args
    assert query['user_id'] == 'alice' and fields['$setOnInsert']['target_price'] == 90
    assert fields['$setOnInsert']['currency'] == 'USD'


@pytest.mark.parametrize('identity,merchant,eligible', [('serpapi:1234567','Store',True), ('serpapi:https://example.com','Store',False), ('serpapi:1234567','',False)])
def test_google_alert_needs_stable_id_and_merchant(identity, merchant, eligible):
    item = {'source': 'serpapi', 'identity': identity, 'product': {'price': 50, 'currency': 'USD', 'merchant': merchant}}
    quote, _ = alerts.eligibility(item)
    assert (quote is not None) is eligible


def test_manual_checks_are_leased_and_owner_scoped(client, mockdb):
    db, _ = mockdb
    db['price_alerts'].find_one.return_value = alert_row()
    db['price_alerts'].find_one_and_update.return_value = None
    assert client.post(f'/api/price-alerts/{ID}/check').status_code == 429
    query = db['price_alerts'].find_one_and_update.call_args.args[0]
    assert query['_id'] == ID and query['user_id'] == 'alice' and query['enabled'] is True
    assert '$lte' in query['next_check_at']


def test_alert_changes_are_owner_scoped(client, mockdb):
    db, _ = mockdb
    assert client.patch(f'/api/price-alerts/{ID}', json={'enabled': False}).status_code == 404
    client.delete(f'/api/price-alerts/{ID}')
    db['price_alerts'].delete_one.assert_called_with({'_id': ID, 'user_id': 'alice'})
    client.patch(f'/api/notifications/{ID}/read')
    assert db['price_notifications'].update_one.call_args.args[0] == {'_id': ID, 'user_id': 'alice'}


def test_catalog_quote_comes_from_verified_catalog():
    catalog = MagicMock()
    catalog.__getitem__.return_value.find_one.return_value = {'id': 'catalog-1', 'price': 80, 'currency': 'USD'}
    with patch.object(alerts.catalog, 'version', return_value={'status':'ready'}), patch.object(alerts.catalog, 'database', return_value=catalog):
        assert alerts.observe_price(alert_row()) == 80
        query = catalog.__getitem__.return_value.find_one.call_args.args[0]
        assert query == {'id': {'$in': ['catalog-1']}}


@pytest.mark.parametrize('candidate', [
    {'id':'serpapi:7654321','merchant':'Store','price':80,'currency':'USD'},
    {'id':'serpapi:1234567','merchant':'Other store','price':80,'currency':'USD'},
    {'id':'serpapi:1234567','merchant':'Store','price':80,'currency':'INR'},
    {'id':'serpapi:1234567','merchant':'Store','price':None,'currency':'USD'},
])
def test_offer_or_currency_mismatch_never_counts_as_a_drop(candidate):
    with patch.object(alerts, 'search_shopping', return_value={'results':[candidate]}):
        with pytest.raises(ValueError):
            alerts.observe_price(alert_row(source='serpapi', identity='serpapi:1234567'))


def test_market_change_does_not_spend_provider_quota():
    with patch.object(alerts, 'search_shopping') as provider:
        with pytest.raises(ValueError):
            alerts.observe_price(alert_row(source='serpapi', market={'SERPAPI_COUNTRY':'different'}))
        provider.assert_not_called()


def test_verified_drop_uses_durable_idempotent_notification(mockdb):
    db, _ = mockdb
    db['price_alerts'].find_one.return_value = alert_row()
    db['price_alerts'].update_one.return_value.matched_count = 1
    with patch.object(alerts, 'observe_price', return_value=80):
        alerts.check_claimed(alert_row())
        first = db['price_notifications'].update_one.call_args
        alerts.check_claimed(alert_row())
        assert db['price_notifications'].update_one.call_args.args[0] == first.args[0]
    selector, notification = first.args
    assert selector['user_id'] == 'alice' and notification['$setOnInsert']['price'] == 80
    assert notification['$setOnInsert']['read'] is False
    # The pending event is persisted atomically with the observed price before delivery.
    first_update = db['price_alerts'].update_one.call_args_list[0].args[1]['$set']
    assert first_update['pending_notification']['price'] == 80 and first_update['min_price'] == 80


def test_unchanged_or_higher_price_does_not_notify(mockdb):
    db, _ = mockdb
    for price, prior in [(100,100), (110,100), (80,80), (95,100)]:
        with patch.object(alerts, 'observe_price', return_value=price):
            alerts.check_claimed(alert_row(min_price=prior))
    db['price_notifications'].update_one.assert_not_called()


def test_stale_worker_cannot_notify_after_pause_or_removal(mockdb):
    db, _ = mockdb
    db['price_alerts'].update_one.return_value.matched_count = 0
    with patch.object(alerts, 'observe_price', return_value=80):
        alerts.check_claimed(alert_row())
    db['price_notifications'].update_one.assert_not_called()
    selector = db['price_alerts'].update_one.call_args.args[0]
    assert selector['enabled'] is True and selector['revision'] == 'version1'


def test_unavailable_quote_keeps_baseline_and_no_notification(mockdb):
    db, _ = mockdb
    with patch.object(alerts, 'observe_price', side_effect=ValueError('Comparable price unavailable')):
        alerts.check_claimed(alert_row())
    fields = db['price_alerts'].update_one.call_args.args[1]['$set']
    assert fields['status'] == 'unavailable' and 'min_price' not in fields
    db['price_notifications'].update_one.assert_not_called()


def test_worker_claims_bounded_batch(mockdb):
    with patch.object(alerts, 'claim_due', side_effect=[alert_row(), None]) as claim, patch.object(alerts, 'check_claimed') as check:
        assert alerts.run_due_checks(max_checks=10) == 1
        assert claim.call_count == 2 and check.call_count == 1


def test_pending_notification_can_be_retried_after_database_failure(mockdb):
    db, _ = mockdb
    row = alert_row(pending_notification={'id':OTHER, 'title':'Headphones','read':False,'price':80})
    db['price_alerts'].find_one.return_value = row
    db['price_notifications'].update_one.side_effect = [ConnectionFailure('temporary'), MagicMock()]
    with pytest.raises(ConnectionFailure):
        alerts.flush_notification(row)
    db['price_alerts'].update_one.assert_not_called()
    alerts.flush_notification(row)
    assert db['price_alerts'].update_one.call_args.args[1] == {'$unset': {'pending_notification': ''}}

"""Regression checks for the cross-project bug review."""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError, ConnectionFailure

from api import main, search_limits, price_alerts
from api.product_prices import price_info
from api.saved_products import public_item
from api.search_service import restore_vectors
from api.auth import require_session
from tests.test_account_features import mockdb, saved_row, ID, OTHER, COL, TIME


@pytest.mark.parametrize('label,currency', [('US$100','USD'),('CA$100','CAD'),('S$100','SGD'),('A$100','AUD'),('NZ$100','NZD'),('$100',None)])
def test_currency_symbols_do_not_overlap(label, currency):
    price = price_info({'price':100,'priceLabel':label})
    assert (price['currency'] if price else None) == currency


def test_naive_mongo_saved_timestamp_is_explicitly_utc():
    value = public_item({'_id':ID,'source':'mongo','identity':'x','product':{},'saved_at':datetime(2026,10,29,23,30)})
    assert value['savedAt'] == '2026-10-29T23:30:00+00:00'


@pytest.mark.parametrize('vectors', [np.ones((1,3),dtype=np.float32),np.array([[float('nan'),0],[0,1]],dtype=np.float32), np.array([[float('inf'),0],[0,1]],dtype=np.float32),np.ones((2,3),dtype=np.float32), np.array([1,2],dtype=np.float32)])
def test_invalid_vector_cache_is_rejected(tmp_path, vectors):
    path=tmp_path/'vectors.npz'; np.savez(path,ids=['a','b'],vectors=vectors)
    with pytest.raises(ValueError): restore_vectors(SimpleNamespace(), [{'id':'a'},{'id':'b'}], path)


def test_vector_cache_dimension_must_match_loaded_model(tmp_path):
    path = tmp_path / 'vectors.npz'
    np.savez(path, ids=['a', 'b'], vectors=np.eye(2, dtype=np.float32))
    model = SimpleNamespace(get_sentence_embedding_dimension=lambda: 3)
    with pytest.raises(ValueError, match='dimension'):
        restore_vectors(SimpleNamespace(_model=model), [{'id': 'a'}, {'id': 'b'}], path)


def test_valid_vector_cache_still_loads(tmp_path):
    path=tmp_path/'vectors.npz'; np.savez(path,ids=['a','b'],vectors=np.eye(2,dtype=np.float32))
    engine=SimpleNamespace(); restore_vectors(engine,[{'id':'a'},{'id':'b'}],path)
    assert engine.index.ntotal == 2


def test_public_health_redacts_internal_details():
    with patch.object(main._search_ready,'is_set',return_value=False),patch.object(main.search_service,'_search_error',None),patch.object(main,'_search_error','private-db.internal:27017 /private/model/path'):
        response=TestClient(main.app).get('/api/health')
        assert response.status_code == 503
        assert 'private-db' not in response.text and '/private/model' not in response.text


def test_collection_batch_has_one_bounded_atomic_write(mockdb):
    db,saved=mockdb
    db['product_collections'].find_one.return_value={'_id':COL,'user_id':'alice','product_ids':[],'name':'X','updated_at':TIME}
    saved.find.return_value=[saved_row(),saved_row(OTHER)]
    old=main.app.dependency_overrides.copy(); main.app.dependency_overrides[require_session]=lambda:{'sub':'alice'}
    try:
        db['product_collections'].update_one.return_value.matched_count=0
        response=TestClient(main.app).put(f'/api/collections/{COL}/products',json={'savedIds':[ID,OTHER]})
        assert response.status_code==409
        query,update=db['product_collections'].update_one.call_args.args
        assert query['user_id']=='alice' and '$expr' in query
        assert update['$addToSet']['product_ids']['$each']==[ID,OTHER]
        assert db['product_collections'].update_one.call_count==1
    finally:
        main.app.dependency_overrides.clear(); main.app.dependency_overrides.update(old)


def test_rate_limit_is_atomic_and_returns_retry_after():
    collection=MagicMock(); collection.find_one_and_update.side_effect=DuplicateKeyError('private details')
    with patch.object(search_limits,'collection',return_value=collection),pytest.raises(HTTPException) as error:
        search_limits.check_search_rate('alice','serpapi')
    assert error.value.status_code==429 and int(error.value.headers['Retry-After'])>=1
    query=collection.find_one_and_update.call_args.args[0]
    assert query['count']['$lt']==5


def test_rate_limit_storage_failure_fails_closed():
    with patch.object(search_limits,'collection',side_effect=ConnectionFailure('private host')),pytest.raises(HTTPException) as error:
        search_limits.check_search_rate('alice','mongo')
    assert error.value.status_code==503 and 'private host' not in error.value.detail


def test_alert_slot_collision_retries_without_exceeding_capacity(mockdb):
    db,_=mockdb
    db['price_alerts'].update_one.side_effect=[DuplicateKeyError('slot already taken'),MagicMock()]
    price_alerts.reserve_active_slot('alice',{'_id':ID,'user_id':'alice','enabled':True})
    calls=db['price_alerts'].update_one.call_args_list
    assert calls[0].args[1]['$setOnInsert']['active_slot']==0
    assert calls[1].args[1]['$setOnInsert']['active_slot']==1


def test_all_alert_slots_full_is_rejected(mockdb):
    db,_=mockdb
    db['price_alerts'].update_one.side_effect=DuplicateKeyError('full')
    with pytest.raises(HTTPException) as error:
        price_alerts.reserve_active_slot('alice',{'_id':ID,'user_id':'alice','enabled':True})
    assert error.value.status_code==409 and db['price_alerts'].update_one.call_count==50

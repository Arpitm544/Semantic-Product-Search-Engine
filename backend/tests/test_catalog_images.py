"""Real catalog photos: safe URLs, import filtering, and attaching photos to results."""
from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import ConnectionFailure

from src.data import catalog
from scripts import import_catalog_images as importer

PHOTO = 'https://m.media-amazon.com/images/I/71abc.jpg'


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    monkeypatch.setattr(catalog, '_images_cache', None)


def images_db(rows):
    db = MagicMock()
    db.__getitem__.return_value.find.return_value = rows
    return db


@pytest.mark.parametrize('url,ok', [
    (PHOTO, True), ('http://m.media-amazon.com/images/I/x.jpg', False),
    ('https://evil.example.com/x.jpg', False), ('javascript:alert(1)', False), (None, False), ('', False),
])
def test_only_https_amazon_image_urls_are_served(url, ok):
    assert catalog.safe_image_url(url) == (url if ok else None)


def test_results_get_photos_and_links_without_overwriting_existing_ones():
    rows = [{'_id': 'esci:us:B07VFKBQ3K', 'image_url': PHOTO},
            {'_id': 'esci:us:B000000002', 'image_url': 'https://evil.example.com/x.jpg'}]
    with patch.object(catalog, 'database', return_value=images_db(rows)):
        payload = catalog.with_product_links({'results': [
            {'id': 'esci:us:B07VFKBQ3K', 'title': 'Headphones'},
            {'id': 'esci:us:B000000002', 'title': 'Unsafe photo'},
            {'id': 'esci:us:B000000003', 'title': 'Has photo', 'imageUrl': 'https://keep.example/x.jpg'},
            {'id': 'serpapi:123', 'title': 'Not catalog'}]})
    first, unsafe, kept, other = payload['results']
    assert first['imageUrl'] == 'https://m.media-amazon.com/images/I/71abc._SL300_.jpg'
    assert first['url'] == 'https://www.amazon.com/dp/B07VFKBQ3K'
    assert 'imageUrl' not in unsafe and unsafe['url'].endswith('/B000000002')
    assert kept['imageUrl'] == 'https://keep.example/x.jpg'
    assert other == {'id': 'serpapi:123', 'title': 'Not catalog'}


def test_photos_are_cached_between_searches():
    db = images_db([{'_id': 'esci:us:B07VFKBQ3K', 'image_url': PHOTO}])
    with patch.object(catalog, 'database', return_value=db):
        catalog.catalog_images()
        catalog.catalog_images()
    assert db.__getitem__.return_value.find.call_count == 1


def test_unreadable_photos_never_break_search():
    db = MagicMock()
    db.__getitem__.return_value.find.side_effect = ConnectionFailure('down')
    with patch.object(catalog, 'database', return_value=db):
        payload = catalog.with_product_links({'results': [{'id': 'esci:us:B07VFKBQ3K', 'title': 'Headphones'}]})
    assert 'imageUrl' not in payload['results'][0] and payload['results'][0]['url']


def test_import_keeps_only_catalog_products_with_safe_photos():
    matches = {
        'B07VFKBQ3K': {'image': PHOTO},
        'B000000002': {'image': 'https://evil.example.com/x.jpg'},
        'B000000003': {'image': None},
        'B0NOTINCAT': {'image': PHOTO},
    }
    catalog_ids = {'esci:us:B07VFKBQ3K', 'esci:us:B000000002', 'esci:us:B000000003'}
    rows, skipped = importer.image_rows(matches, catalog_ids)
    assert [row['_id'] for row in rows] == ['esci:us:B07VFKBQ3K']
    assert rows[0]['image_url'] == PHOTO and rows[0]['source'] == 'amazon-reviews-2023'
    assert skipped == {'not_in_catalog': 1, 'no_or_unsafe_image': 2}


def test_import_writes_to_the_separate_collection_and_can_clear():
    db = MagicMock()
    db.name = 'semantic_product_search'
    collections = {'amazon_products': MagicMock(), 'catalog_images': MagicMock()}
    collections['amazon_products'].distinct.return_value = ['esci:us:B07VFKBQ3K']
    db.__getitem__.side_effect = lambda name: collections[name]
    summary = importer.import_images(db, {'B07VFKBQ3K': {'image': PHOTO}}, clear=True)
    collections['catalog_images'].delete_many.assert_called_once_with({})
    (ops,), _ = collections['catalog_images'].bulk_write.call_args
    assert len(ops) == 1 and summary['imported'] == 1 and summary['catalog_size'] == 1
    collections['amazon_products'].bulk_write.assert_not_called()


@pytest.mark.parametrize('url,expected', [
    ('https://m.media-amazon.com/images/I/61vR9d7nDhL._SL1200_.jpg', 'https://m.media-amazon.com/images/I/61vR9d7nDhL._SL300_.jpg'),
    ('https://m.media-amazon.com/images/I/41x._AC_UL1500_.png', 'https://m.media-amazon.com/images/I/41x._SL300_.png'),
    ('https://m.media-amazon.com/images/I/71abc.jpg', 'https://m.media-amazon.com/images/I/71abc._SL300_.jpg'),
])
def test_search_results_use_small_thumbnails(url, expected):
    assert catalog.sized_image_url(url) == expected

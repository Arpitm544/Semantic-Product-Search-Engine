"""Import real product photos for the catalog into the `catalog_images` collection.

The photos come from a match file of {ASIN: {"image": url, ...}}, built by streaming
the Amazon Reviews 2023 item metadata (McAuley Lab) and matching it to catalog
ASINs. Product records are not modified: photos live in their own collection, so
the catalog fingerprint and Atlas vectors are unaffected, and removing the
collection (or running with --clear) brings back the illustrations.

Usage, from backend/:
    .venv/bin/python scripts/import_catalog_images.py matches.json [--clear]

Note: the photo URLs point to Amazon's image servers and come from a research
dataset. That suits demos and portfolios; for a public commercial site, use
Amazon's official API instead.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pymongo import ReplaceOne  # noqa: E402

from src.data.catalog import COLLECTION, IMAGES_COLLECTION, database, safe_image_url  # noqa: E402

SOURCE = 'amazon-reviews-2023'


def image_rows(matches, catalog_ids):
    """Valid rows for catalog products with a safe photo URL, plus skip counts."""
    rows, skipped = [], {'not_in_catalog': 0, 'no_or_unsafe_image': 0}
    imported_at = datetime.now(timezone.utc)
    for asin, match in matches.items():
        product_id = f'esci:us:{asin}'
        if product_id not in catalog_ids:
            skipped['not_in_catalog'] += 1
            continue
        url = safe_image_url((match or {}).get('image'))
        if not url:
            skipped['no_or_unsafe_image'] += 1
            continue
        rows.append({'_id': product_id, 'image_url': url, 'source': SOURCE, 'imported_at': imported_at})
    return rows, skipped


def import_images(db, matches, clear=False):
    catalog_ids = set(db[COLLECTION].distinct('id'))
    rows, skipped = image_rows(matches, catalog_ids)
    images = db[IMAGES_COLLECTION]
    if clear:
        images.delete_many({})
    for offset in range(0, len(rows), 1000):
        images.bulk_write([ReplaceOne({'_id': row['_id']}, row, upsert=True) for row in rows[offset:offset + 1000]],
                          ordered=False)
    return {'imported': len(rows), **skipped, 'catalog_size': len(catalog_ids),
            'collection': f'{db.name}.{IMAGES_COLLECTION}'}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('matches', type=Path, help='JSON file of {ASIN: {"image": url, ...}}')
    parser.add_argument('--clear', action='store_true', help='Remove existing photos before importing')
    args = parser.parse_args()
    summary = import_images(database(), json.loads(args.matches.read_text()), clear=args.clear)
    share = summary['imported'] / max(1, summary['catalog_size'])
    print(f"Imported {summary['imported']:,} photos into {summary['collection']} "
          f"({share:.0%} of {summary['catalog_size']:,} catalog products). "
          f"Skipped: {summary['not_in_catalog']} not in catalog, {summary['no_or_unsafe_image']} without a usable photo.")


if __name__ == '__main__':
    main()

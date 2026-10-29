"""Bounded canonical product text and stable source IDs."""
import hashlib
import json


def map_product(product, shop):
    options = {o['name'][:80]: [str(v)[:100] for v in o.get('values', [])[:100]]
               for o in product.get('options', [])[:10]}
    record = dict(id=f"shopify:{shop}:{product['id'].rsplit('/', 1)[-1]}",
                  shop_domain=shop, product_gid=product['id'],
                  title=product.get('title', '')[:512], description=product.get('description', '')[:6000],
                  category=product.get('productType', '')[:200], brand=product.get('vendor', '')[:200],
                  tags=[str(t)[:100] for t in product.get('tags', [])[:50]], options=options,
                  eligible=product.get('status') == 'ACTIVE', shopify_updated_at=product.get('updatedAt'))
    record['representation_text'] = (f"[Title] {record['title']} | [Brand] {record['brand']} | "
                                     f"[Category] {record['category']} | [Description] {record['description']} | "
                                     f"[Options] {json.dumps(options, sort_keys=True)} | [Tags] {' '.join(record['tags'])}")
    record['text_hash'] = hashlib.sha256(record['representation_text'].encode()).hexdigest()
    return record

"""Verify raw-body Shopify deliveries before durable enqueue."""
import base64
import hashlib
import hmac

TOPICS = {'products/create', 'products/update', 'products/delete',
          'collections/update', 'collections/delete', 'product_listings/add',
          'product_listings/update', 'product_listings/remove'}


def verify(body, signature, secret):
    if not secret or not signature:
        return False
    expected = base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(expected, signature)

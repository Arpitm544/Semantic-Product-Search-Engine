"""Bounded Shopify GraphQL transport; never expose upstream bodies or tokens."""
import time
import httpx


class ShopifyError(RuntimeError):
    pass


class Client:
    def __init__(self, settings):
        self.settings = settings

    def query(self, query, variables=None, storefront=False):
        s = self.settings
        path = 'api' if storefront else 'admin/api'
        header = 'Shopify-Storefront-Private-Token' if storefront else 'X-Shopify-Access-Token'
        token = s.storefront_token if storefront else s.admin_token
        for attempt in range(4):
            try:
                response = httpx.post(f'https://{s.shop}/{path}/{s.version}/graphql.json',
                                      headers={header: token}, json={'query': query, 'variables': variables or {}},
                                      timeout=20, follow_redirects=False)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < 3:
                        time.sleep(2 ** attempt)
                        continue
                if response.status_code != 200:
                    raise ShopifyError('Shopify request failed. Check store access and worker logs.')
                payload = response.json()
                errors = payload.get('errors', [])
                if errors and all(e.get('extensions', {}).get('code') == 'THROTTLED' for e in errors) and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                if errors or not isinstance(payload.get('data'), dict):
                    raise ShopifyError('Shopify returned an incomplete GraphQL response.')
                return payload['data']
            except (httpx.HTTPError, ValueError) as error:
                if attempt == 3:
                    raise ShopifyError('Shopify is temporarily unreachable.') from error
                time.sleep(2 ** attempt)
        raise ShopifyError('Shopify request exhausted retries.')

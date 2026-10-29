"""Single-store Shopify settings. Secrets never leave the backend."""
import os
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    shop: str = field(default_factory=lambda: os.getenv('SHOPIFY_SHOP_DOMAIN', ''))
    admin_token: str = field(default_factory=lambda: os.getenv('SHOPIFY_ADMIN_ACCESS_TOKEN', ''), repr=False)
    storefront_token: str = field(default_factory=lambda: os.getenv('SHOPIFY_STOREFRONT_PRIVATE_TOKEN', ''), repr=False)
    secret: str = field(default_factory=lambda: os.getenv('SHOPIFY_WEBHOOK_SECRET', ''), repr=False)
    version: str = field(default_factory=lambda: os.getenv('SHOPIFY_API_VERSION', '2026-10'))
    collection: str = field(default_factory=lambda: os.getenv('SHOPIFY_COLLECTION_GID', ''))
    cap: int = field(default_factory=lambda: int(os.getenv('SHOPIFY_SYNC_MAX_PRODUCTS', '500')))
    ttl: int = field(default_factory=lambda: int(os.getenv('SHOPIFY_HYDRATION_TTL_SECONDS', '60')))

    def validate(self):
        if os.getenv('SHOPIFY_ENABLED', 'false').lower() != 'true':
            raise ValueError('Shopify is disabled. Configure the backend first.')
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*\.myshopify\.com', self.shop):
            raise ValueError('Invalid Shopify store domain.')
        if not self.admin_token or not self.storefront_token or not self.collection:
            raise ValueError('Shopify credentials and collection are required.')
        if not re.fullmatch(r'\d{4}-(01|04|07|10)', self.version) or self.cap < 1 or not 0 <= self.ttl <= 300:
            raise ValueError('Invalid Shopify version, product cap, or cache TTL.')
        return self

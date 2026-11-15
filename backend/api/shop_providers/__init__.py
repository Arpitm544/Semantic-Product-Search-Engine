"""Free online-shop providers. A provider is enabled once its keys or stores are set."""
from api.shop_providers import ebay
from api.shop_providers.stores import configured_stores

PROVIDERS = {provider.NAME: provider for provider in (ebay,)}


def enabled_providers():
    return [provider for provider in PROVIDERS.values() if provider.configured()] + configured_stores()

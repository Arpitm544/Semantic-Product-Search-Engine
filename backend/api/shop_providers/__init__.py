"""Free online-shop providers. A provider is enabled once its keys are set."""
from api.shop_providers import ebay, flipkart

PROVIDERS = {provider.NAME: provider for provider in (ebay, flipkart)}


def enabled_providers():
    return [provider for provider in PROVIDERS.values() if provider.configured()]

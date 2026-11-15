"""Conservative price and currency handling shared by filters and alerts."""
from decimal import Decimal, InvalidOperation
import re

CURRENCIES = {'INR', 'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'NZD', 'SGD', 'AED', 'CHF', 'JPY', 'CNY', 'HKD', 'SEK', 'NOK', 'DKK'}


def numeric(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = Decimal(str(value))
        return float(number) if number.is_finite() and 0 <= number <= Decimal('1e12') else None
    except (InvalidOperation, ValueError, OverflowError):
        return None


def label_currencies(label):
    explicit = {value for value in CURRENCIES if re.search(r'\b' + value + r'\b', label, re.I)}
    tokens = {'₹': 'INR', '€': 'EUR', '£': 'GBP', 'US$': 'USD', 'CA$': 'CAD',
              'A$': 'AUD', 'NZ$': 'NZD', 'S$': 'SGD', 'HK$': 'HKD'}
    # Longest tokens prevent US$ matching S$, or CA$ matching A$.
    pattern = '|'.join(re.escape(symbol) for symbol in sorted(tokens, key=len, reverse=True))
    return explicit | {tokens[match.group()] for match in re.finditer(pattern, label)}


def currency_of(product):
    code = str(product.get('currency') or '').upper().strip()
    found = label_currencies(str(product.get('priceLabel') or ''))
    if not code:
        return found.pop() if len(found) == 1 else None
    if code not in CURRENCIES:
        return None
    if found and found != {code}:
        return None
    return code


def price_info(product):
    amount, currency = numeric(product.get('price')), currency_of(product)
    if amount is None or currency is None:
        return None
    return {'amount': amount, 'currency': currency}


def matches_budget(product, preferences):
    low, high = preferences['minBudget'], preferences['maxBudget']
    if low is None and high is None:
        return True
    price = price_info(product)
    if not price:
        return False
    if price['currency'] != preferences['currency']:
        return False
    return within_budget(price['amount'], low, high)


def within_budget(amount, low, high):
    if low is not None and amount < low:
        return False
    return high is None or amount <= high


def matches_detail(product, field, values):
    if not values:
        return True
    return str(product.get(field) or '').casefold() in {v.casefold() for v in values}


def matches_stock(product, required):
    if not required:
        return True
    stock = numeric(product.get('stock'))
    return stock is not None and stock > 0


FILTERS = {
    'budget': lambda product, preferences: matches_budget(product, preferences),
    'categories': lambda product, preferences: matches_detail(product, 'category', preferences['categories']),
    'brands': lambda product, preferences: matches_detail(product, 'brand', preferences['brands']),
    'inStockOnly': lambda product, preferences: matches_stock(product, preferences['inStockOnly']),
}
FILTER_LABELS = {'budget': 'budget', 'categories': 'category', 'brands': 'brand', 'inStockOnly': 'in-stock'}
# Only filter on details a source actually provides. The Amazon catalog has
# brands and categories but no prices or stock; Google Shopping results have
# prices but no brand, category, or stock fields.
SOURCE_FILTERS = {'mongo': {'categories', 'brands'}, 'serpapi': {'budget'}}
SOURCE_NAMES = {'mongo': 'catalog', 'serpapi': 'Google Shopping'}


def active_filters(preferences):
    active = {
        'budget': preferences['minBudget'] is not None or preferences['maxBudget'] is not None,
        'categories': bool(preferences['categories']),
        'brands': bool(preferences['brands']),
        'inStockOnly': bool(preferences['inStockOnly']),
    }
    return [name for name in FILTERS if active[name]]


def matches_preferences(product, preferences, filters=tuple(FILTERS)):
    return all(FILTERS[name](product, preferences) for name in filters)


def skipped_notice(skipped, source):
    labels = [FILTER_LABELS[name] for name in skipped]
    names = labels[0] if len(labels) == 1 else ', '.join(labels[:-1]) + ' and ' + labels[-1]
    plural = 'filters were' if len(labels) > 1 else 'filter was'
    return (f'Your {names} {plural} not applied because {SOURCE_NAMES.get(source, source)} '
            'results do not include those details.')


def apply_preferences(payload, preferences, source=None):
    """Filter results by saved preferences the source has data for.

    With no source, every active filter applies.
    """
    active = active_filters(preferences)
    supported = SOURCE_FILTERS.get(source, set(FILTERS)) if source else set(FILTERS)
    applied = [name for name in active if name in supported]
    skipped = [name for name in active if name not in supported]
    results = [item for item in payload.get('results', []) if matches_preferences(item, preferences, applied)]
    notices = [payload.get('warning')]
    if applied:
        notices.append('Saved preferences filter the returned candidates. Products with unavailable details for an active filter are excluded.')
    if skipped:
        notices.append(skipped_notice(skipped, source))
    return {**payload, 'results': results, 'preferencesApplied': True,
            'appliedPreferences': applied, 'skippedPreferences': skipped,
            'warning': ' '.join(filter(None, notices))}

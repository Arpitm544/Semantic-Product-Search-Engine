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
    if low is not None and price['amount'] < low:
        return False
    return high is None or price['amount'] <= high


def matches_detail(product, field, values):
    if not values:
        return True
    return str(product.get(field) or '').casefold() in {v.casefold() for v in values}


def matches_stock(product, required):
    if not required:
        return True
    stock = numeric(product.get('stock'))
    return stock is not None and stock > 0


def matches_preferences(product, preferences):
    return all((matches_budget(product, preferences),
                matches_detail(product, 'category', preferences['categories']),
                matches_detail(product, 'brand', preferences['brands']),
                matches_stock(product, preferences['inStockOnly'])))


def apply_preferences(payload, preferences):
    results = [item for item in payload.get('results', []) if matches_preferences(item, preferences)]
    notice = 'Saved preferences filter the returned candidates. Products with unavailable details for an active filter are excluded.'
    return {**payload, 'results': results, 'preferencesApplied': True,
            'warning': ' '.join(filter(None, [payload.get('warning'), notice]))}

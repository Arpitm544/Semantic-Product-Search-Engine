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


def currency_of(product):
    code = str(product.get('currency') or '').upper().strip()
    label = str(product.get('priceLabel') or '')
    explicit = {value for value in CURRENCIES if re.search(r'\b' + value + r'\b', label, re.I)}
    symbols = [('₹', 'INR'), ('€', 'EUR'), ('£', 'GBP'), ('US$', 'USD'), ('CA$', 'CAD'), ('A$', 'AUD'), ('NZ$', 'NZD'), ('S$', 'SGD'), ('HK$', 'HKD')]
    found = explicit | {currency for symbol, currency in symbols if symbol in label}
    if code:
        return code if code in CURRENCIES and (not found or found == {code}) else None
    return found.pop() if len(found) == 1 else None


def price_info(product):
    amount, currency = numeric(product.get('price')), currency_of(product)
    if amount is None or currency is None:
        return None
    return {'amount': amount, 'currency': currency}


def within_budget(product, preferences):
    minimum, maximum = preferences['minBudget'], preferences['maxBudget']
    if minimum is None and maximum is None:
        return True
    price = price_info(product)
    if not price or price['currency'] != preferences['currency']:
        return False
    return price_in_range(price['amount'], minimum, maximum)


def price_in_range(amount, minimum, maximum):
    if minimum is not None and amount < minimum:
        return False
    if maximum is not None and amount > maximum:
        return False
    return True


def matches_detail(product, field, values):
    if not values:
        return True
    return str(product.get(field) or '').casefold() in {v.casefold() for v in values}


def matches_stock(product, preferences):
    if not preferences['inStockOnly']:
        return True
    stock = numeric(product.get('stock'))
    return stock is not None and stock > 0


def matches_preferences(product, preferences):
    return all((within_budget(product, preferences),
                matches_detail(product, 'category', preferences['categories']),
                matches_detail(product, 'brand', preferences['brands']),
                matches_stock(product, preferences)))


def apply_preferences(payload, preferences):
    results = [item for item in payload.get('results', []) if matches_preferences(item, preferences)]
    notice = 'Saved preferences filter the returned candidates. Products with unavailable details for an active filter are excluded.'
    return {**payload, 'results': results, 'preferencesApplied': True,
            'warning': ' '.join(filter(None, [payload.get('warning'), notice]))}

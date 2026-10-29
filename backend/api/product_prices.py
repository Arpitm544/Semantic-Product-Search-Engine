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
    # Match longest tokens first, so US$ cannot also match S$, nor CA$ A$.
    tokens = dict(symbols)
    pattern = '|'.join(re.escape(symbol) for symbol in sorted(tokens, key=len, reverse=True))
    found = explicit | {tokens[match.group()] for match in re.finditer(pattern, label)}
    if code:
        return code if code in CURRENCIES and (not found or found == {code}) else None
    return found.pop() if len(found) == 1 else None


def price_info(product):
    amount, currency = numeric(product.get('price')), currency_of(product)
    if amount is None or currency is None:
        return None
    return {'amount': amount, 'currency': currency}


def apply_preferences(payload, preferences):
    def matches(product):
        if preferences['minBudget'] is not None or preferences['maxBudget'] is not None:
            price = price_info(product)
            if not price or price['currency'] != preferences['currency']:
                return False
            if preferences['minBudget'] is not None and price['amount'] < preferences['minBudget']:
                return False
            if preferences['maxBudget'] is not None and price['amount'] > preferences['maxBudget']:
                return False
        for field, values in [('category', preferences['categories']), ('brand', preferences['brands'])]:
            if values and str(product.get(field) or '').casefold() not in {v.casefold() for v in values}:
                return False
        if preferences['inStockOnly']:
            stock = numeric(product.get('stock'))
            if stock is None or stock <= 0:
                return False
        return True
    results = [item for item in payload.get('results', []) if matches(item)]
    notice = 'Saved preferences filter the returned candidates. Products with unavailable details for an active filter are excluded.'
    return {**payload, 'results': results, 'preferencesApplied': True,
            'warning': ' '.join(filter(None, [payload.get('warning'), notice]))}

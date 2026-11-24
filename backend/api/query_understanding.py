"""Turn what a shopper typed into search text, a price filter and narrowing chips.

Price limits ("under $100") are applied automatically wherever results carry
prices. Brands and colors are offered as one-click chips instead of being
applied silently: on Amazon ESCI test searches, forcing them as filters
lowered ranking quality (NDCG@10 0.715 -> 0.654), because the search already
uses those words well. A chip the shopper clicks is applied strictly.
"""
from dataclasses import dataclass
import logging
from threading import Lock

from api.product_prices import price_info
from src.search.query_filters import (
    BrandIndex, COLORS, FILTER_TYPES, has_brand, has_color, normalize_brand, parse_query, price_label,
)

PRICED_SOURCES = {"serpapi", "shops"}
_brand_cache = {"products": None, "index": None}
_brand_lock = Lock()


def brand_index(products):
    """Build the brand vocabulary once per catalog list.

    Brand chips are optional: without a usable catalog, search still runs."""
    if not isinstance(products, list) or not products:
        return None
    with _brand_lock:
        if _brand_cache["products"] is not products:
            try:
                index = BrandIndex(products)
            except (TypeError, KeyError, AttributeError):
                logging.getLogger(__name__).exception("Brand index could not be built")
                index = None
            _brand_cache.update(products=products, index=index)
        return _brand_cache["index"]


def parse_skip(value):
    return frozenset(item for item in (value or "").split(",") if item in FILTER_TYPES)


@dataclass(frozen=True)
class FilterChoice:
    """Smart-filter choices sent with a search: types switched off and chips picked."""
    skip: frozenset = frozenset()
    brand: str = ""
    color: str = ""


def filter_choice(skip: str = "", brand: str = "", color: str = "") -> FilterChoice:
    """Read the choices from query parameters (used as a FastAPI dependency)."""
    return FilterChoice(parse_skip(skip), brand[:100], color[:30])


NO_CHOICE = FilterChoice()


def _chosen_brand(brand, brands):
    name = brand.strip()
    if not name:
        return None
    value = normalize_brand(name)
    label = brands.display.get(value, name) if brands else name
    return {"type": "brand", "value": value, "label": label}


def _chosen_color(color):
    value = COLORS.get(color.strip().lower())
    return {"type": "color", "value": value, "label": value.capitalize()} if value else None


def _suggestions(found, active):
    """Detected brand and color the shopper has not already chosen."""
    chosen = {item["type"] for item in active}
    return [{"type": kind, "value": found[kind]["value"],
             "label": found[kind].get("label") or found[kind]["value"].capitalize()}
            for kind in ("brand", "color") if kind in found and kind not in chosen]


def _price(found, source):
    if "price" not in found:
        return None
    return {**found["price"], "label": price_label(found["price"]), "applied": source in PRICED_SOURCES}


def understand(query, source, brands=None, choice=NO_CHOICE):
    """Describe the query for the page and decide which filters apply."""
    parsed = parse_query(query, brands, choice.skip)
    active = [item for item in (_chosen_brand(choice.brand, brands), _chosen_color(choice.color)) if item]
    return {
        "searchText": parsed["text"],
        "price": _price(parsed["filters"], source),
        "active": active,
        "suggestions": _suggestions(parsed["filters"], active),
    }


def price_applies(price):
    return bool(price) and price["applied"]


def _in_range(amount, low, high):
    if low is not None and amount < low:
        return False
    return high is None or amount <= high


def _other_currency(info, price):
    return bool(price["currency"]) and info["currency"] != price["currency"]


def within_price(product, price):
    """Products without a usable price are left out while a price filter applies."""
    if not price_applies(price):
        return True
    info = price_info(product)
    if info is None or _other_currency(info, price):
        return False
    return _in_range(info["amount"], price["min"], price["max"])


CHIP_TESTS = {"brand": has_brand, "color": has_color}


def matches(product, understanding):
    """True when the product passes every filter that applies."""
    if not within_price(product, understanding["price"]):
        return False
    return all(CHIP_TESTS[item["type"]](product, item["value"]) for item in understanding["active"])


def filtering(understanding):
    return bool(understanding["active"]) or price_applies(understanding["price"])


def understood(understanding):
    return any(understanding[key] for key in ("price", "active", "suggestions"))


def _limited(results, limit):
    return results[:limit] if limit else results


def _notes(payload, price):
    notes = [payload.get("warning")]
    if price and not price["applied"]:
        notes.append(f"{price['label']} was not applied: catalog products have no prices. "
                     "Choose Online shops or Google Shopping to filter by price.")
    elif price and price["currency"]:
        notes.append(f"Only products priced in {price['currency']} are shown for {price['label']}.")
    return " ".join(filter(None, notes))


def apply(payload, understanding, limit=None):
    """Filter a search payload and attach what was understood.

    A plain query with nothing to understand leaves the payload unchanged."""
    results = payload.get("results", [])
    if not understood(understanding):
        return {**payload, "results": _limited(results, limit)} if limit else payload
    narrowing = filtering(understanding)
    if narrowing:
        results = [product for product in results if matches(product, understanding)]
    updated = {**payload, "results": _limited(results, limit), "queryFilters": understanding}
    warning = _notes(payload, understanding["price"])
    if warning:
        updated["warning"] = warning
    if narrowing and "candidateCount" in payload:
        updated["candidateCount"] = len(results)
    return updated

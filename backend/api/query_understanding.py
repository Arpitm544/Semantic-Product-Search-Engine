"""Turn what a shopper typed into search text, a price filter and narrowing chips.

Price limits ("under $100") are applied automatically wherever results carry
prices. Brands and colors are offered as one-click chips instead of being
applied silently: on Amazon ESCI test searches, forcing them as filters
lowered ranking quality (NDCG@10 0.715 -> 0.654), because the search already
uses those words well. A chip the shopper clicks is applied strictly.
"""
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
    return {item for item in (value or "").split(",") if item in FILTER_TYPES}


def understand(query, source, brands=None, skip=(), brand="", color=""):
    """Describe the query for the page and decide which filters apply."""
    parsed = parse_query(query, brands, skip)
    found = parsed["filters"]
    active = []
    if brand.strip():
        value = normalize_brand(brand)
        label = brands.display.get(value, brand.strip()) if brands else brand.strip()
        active.append({"type": "brand", "value": value, "label": label})
    if color.strip().lower() in COLORS:
        value = COLORS[color.strip().lower()]
        active.append({"type": "color", "value": value, "label": value.capitalize()})
    active_types = {item["type"] for item in active}
    suggestions = [
        {"type": kind, "value": found[kind]["value"],
         "label": found[kind].get("label") or found[kind]["value"].capitalize()}
        for kind in ("brand", "color") if kind in found and kind not in active_types
    ]
    price = None
    if "price" in found:
        price = {**found["price"], "label": price_label(found["price"]),
                 "applied": source in PRICED_SOURCES}
    return {
        "searchText": parsed["text"],
        "price": price,
        "active": active,
        "suggestions": suggestions,
    }


def matches(product, understanding):
    """True when the product passes every filter that applies."""
    price = understanding["price"]
    if price and price["applied"]:
        info = price_info(product)
        if info is None:
            return False
        if price["currency"] and info["currency"] != price["currency"]:
            return False
        if price["min"] is not None and info["amount"] < price["min"]:
            return False
        if price["max"] is not None and info["amount"] > price["max"]:
            return False
    for item in understanding["active"]:
        if item["type"] == "brand" and not has_brand(product, item["value"]):
            return False
        if item["type"] == "color" and not has_color(product, item["value"]):
            return False
    return True


def filtering(understanding):
    return bool(understanding["active"]) or bool(understanding["price"] and understanding["price"]["applied"])


def apply(payload, understanding, limit=None):
    """Filter a search payload and attach what was understood.

    A plain query with nothing to understand leaves the payload unchanged."""
    if not (understanding["price"] or understanding["active"] or understanding["suggestions"]):
        return {**payload, "results": payload.get("results", [])[:limit]} if limit else payload
    results = payload.get("results", [])
    if filtering(understanding):
        results = [product for product in results if matches(product, understanding)]
    notes = [payload.get("warning")]
    price = understanding["price"]
    if price and not price["applied"]:
        notes.append(f"{price['label']} was not applied: catalog products have no prices. "
                     "Choose Online shops or Google Shopping to filter by price.")
    elif price and price["currency"]:
        notes.append(f"Only products priced in {price['currency']} are shown for {price['label']}.")
    payload = {**payload, "results": results[:limit] if limit else results, "queryFilters": understanding}
    if any(notes):
        payload["warning"] = " ".join(filter(None, notes))
    if filtering(understanding) and "candidateCount" in payload:
        payload["candidateCount"] = len(results)
    return payload

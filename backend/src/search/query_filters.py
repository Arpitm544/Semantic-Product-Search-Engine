"""Read filters people type into a search: price limits, brands and colors.

    "black nike running shoes under $100"
        -> search text "black nike running shoes"
        -> price at most 100 USD, brand Nike, color black

Price phrases are removed from the search text because they only add noise
to retrieval. Brand and color words stay in the text, since they also help
find the right products; they additionally become strict filters.

Brands are learned from the catalog, not from a fixed list. A word only
counts as a brand when the shopper signals it ("by sony", "from nike",
"sony brand") or when the catalog shows the word almost always means that
brand. "nike" qualifies; "apple" in "apple juice" does not, because many
products mention apples without being Apple products.
"""

from collections import Counter, defaultdict
import re

# ------------------------------------------------------------------ price

CURRENCY_WORDS = {
    "$": "USD", "usd": "USD", "dollar": "USD", "dollars": "USD", "bucks": "USD",
    "₹": "INR", "rs": "INR", "rs.": "INR", "inr": "INR", "rupee": "INR", "rupees": "INR",
    "€": "EUR", "eur": "EUR", "euro": "EUR", "euros": "EUR",
    "£": "GBP", "gbp": "GBP", "pound": "GBP", "pounds": "GBP",
}
_CURRENCY = r"(?:\$|₹|€|£|rs\.?|usd|inr|eur|gbp|dollars?|bucks|rupees?|euros?|pounds?)"
# 1,299 · 49.99 · 2k
_AMOUNT = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?k?"
_MONEY = rf"(?:(?P<@pre>{_CURRENCY})\s*)?(?P<@num>{_AMOUNT})(?:\s*(?P<@post>{_CURRENCY}))?"


def _money(prefix):
    return _MONEY.replace("@", prefix)


_UPPER_WORDS = r"under|below|less\s+than|cheaper\s+than|at\s+most|up\s+to|upto|within|no\s+more\s+than|<=?"
_LOWER_WORDS = r"over|above|more\s+than|at\s+least|starting\s+(?:at|from)|>=?"
PRICE_PATTERNS = (
    ("range", re.compile(rf"(?:(?<=\s)|^)(?:between\s+)?{_money('a')}\s*(?:-|–|to|and)\s*{_money('b')}(?=\s|$)", re.I)),
    ("max", re.compile(rf"(?:\b|(?<=\s)|^)(?:{_UPPER_WORDS})\s*{_money('a')}(?=\s|$)", re.I)),
    ("min", re.compile(rf"(?:\b|(?<=\s)|^)(?:{_LOWER_WORDS})\s*{_money('a')}(?=\s|$)", re.I)),
)


# A number followed by one of these is a size, count or age, not a price:
# "up to 6 people", "under 2 years", "over 64 gb".
UNITS = {
    "people", "person", "persons", "player", "players", "year", "years", "yr", "yrs", "month", "months",
    "week", "weeks", "day", "days", "hour", "hours", "hr", "hrs", "minute", "minutes", "min", "mins",
    "kg", "kgs", "g", "gram", "grams", "lb", "lbs", "pound", "oz", "ounce", "ounces", "ml", "l", "liter",
    "liters", "litre", "litres", "gallon", "gallons", "gb", "tb", "mb", "inch", "inches", "in", "ft", "feet",
    "foot", "mm", "cm", "m", "meter", "meters", "w", "watt", "watts", "v", "volt", "volts", "mah", "hz",
    "pack", "packs", "pcs", "pc", "piece", "pieces", "count", "ct", "x", "sheets", "pages", "pairs",
    "cups", "seats", "seater", "rooms", "sq", "degree", "degrees", "percent", "%",
}


def _next_word(text, end):
    match = re.match(r"\s*([a-z%]+)", text[end:], re.I)
    return match.group(1).lower() if match else ""


def _amount(text):
    text = text.lower().replace(",", "")
    multiplier = 1000 if text.endswith("k") else 1
    return float(text.rstrip("k")) * multiplier


def _currency(match, prefix):
    for part in ("pre", "post"):
        word = match.group(f"{prefix}{part}")
        if word:
            return CURRENCY_WORDS.get(word.lower())
    return None


def parse_price(text):
    """Return (price filter or None, text without the price phrase)."""
    for kind, pattern in PRICE_PATTERNS:
        for match in pattern.finditer(text):
            if _next_word(text, match.end()) in UNITS:
                continue
            if kind == "range":
                # A bare "1-2" or "2 to 4" is often a size or count ("2 to 4 years").
                # Ranges need a currency or the word "between" to count as prices.
                currencies = {_currency(match, "a"), _currency(match, "b")} - {None}
                if not currencies and not match.group(0).lower().startswith("between"):
                    continue
                low, high = sorted((_amount(match.group("anum")), _amount(match.group("bnum"))))
                price = {"min": low, "max": high, "currency": currencies.pop() if len(currencies) == 1 else None}
            else:
                amount = _amount(match.group("anum"))
                price = {"min": amount if kind == "min" else None,
                         "max": amount if kind == "max" else None,
                         "currency": _currency(match, "a")}
            price["text"] = match.group(0).strip()
            remaining = (text[:match.start()] + " " + text[match.end():]).strip()
            return price, re.sub(r"\s+", " ", remaining)
    return None, text


# ------------------------------------------------------------------ color

COLORS = {
    "black": "black", "white": "white", "red": "red", "blue": "blue", "navy": "navy",
    "green": "green", "olive": "olive", "yellow": "yellow", "orange": "orange",
    "pink": "pink", "purple": "purple", "violet": "purple", "brown": "brown",
    "beige": "beige", "tan": "tan", "grey": "gray", "gray": "gray", "silver": "silver",
    "gold": "gold", "golden": "gold", "maroon": "maroon", "teal": "teal", "khaki": "khaki",
    "ivory": "ivory", "turquoise": "turquoise", "burgundy": "burgundy",
}
# Words a product text may use for each canonical color.
COLOR_SPELLINGS = defaultdict(set)
for _word, _canonical in COLORS.items():
    COLOR_SPELLINGS[_canonical].add(_word)


def parse_color(text):
    """One clear color word becomes a filter. Several colors are left to search."""
    found = {COLORS[word] for word in re.findall(r"[a-z]+", text.lower()) if word in COLORS}
    if len(found) != 1:
        return None
    color = found.pop()
    return {"value": color}


def has_color(product, color):
    words = set(re.findall(r"[a-z]+", product_text(product).lower()))
    return bool(words & COLOR_SPELLINGS[color])


# ------------------------------------------------------------------ brand

BRAND_CUE = re.compile(r"\b(?:by|from|brand)\s+(?=[a-z0-9])", re.I)
SUFFIXES = {"inc", "llc", "ltd", "co", "corp", "corporation", "company", "store", "official"}
ACCESSORY_WORDS = {
    "replacement", "replacements", "compatible", "compatibility", "fits", "fit", "refill", "refills",
    "accessory", "accessories", "part", "parts", "case", "cases", "cover", "covers", "charger",
    "chargers", "band", "bands", "strap", "straps", "filter", "filters", "cartridge", "cartridges",
    "adapter", "adapters", "skin", "skins", "protector", "protectors", "mount", "mounts", "holder",
    "battery", "batteries", "remote", "toner", "ink", "lens", "lenses", "blade", "blades", "pad", "pads",
}
PLACEHOLDER_BRANDS = {"generic", "unknown", "unbranded", "na", "n a", "none", "no brand", "brand"}


def normalize_brand(value):
    words = re.findall(r"[a-z0-9]+", str(value or "").lower().replace("&", " and "))
    while words and words[-1] in SUFFIXES:
        words.pop()
    return " ".join(words)


def product_text(product):
    return f"{product.get('title', '')} {product.get('representation_text') or product.get('description', '')}"


class BrandIndex:
    """Brand names the catalog knows, and how reliably each word means a brand."""

    MIN_PRODUCTS = 5      # ignore brands with too few products to trust
    MIN_PRECISION = 0.5   # unprompted, a word must mean the brand at least half the time

    def __init__(self, products):
        self.prefix_counts = Counter()   # "samsung" covers "samsung electronics"
        self.full_counts = Counter()     # exact brand names only
        self.display = {}
        self.title_tokens = defaultdict(set)
        for index, product in enumerate(products):
            brand = normalize_brand(product.get("brand"))
            if brand and brand not in PLACEHOLDER_BRANDS:
                words = brand.split()
                self.full_counts[brand] += 1
                for size in range(1, min(3, len(words)) + 1):
                    prefix = " ".join(words[:size])
                    self.prefix_counts[prefix] += 1
                    self.display.setdefault(prefix, str(product["brand"]).strip() if size == len(words) else prefix.title())
            for token in set(re.findall(r"[a-z0-9]+", str(product.get("title", "")).lower())):
                self.title_tokens[token].add(index)
        self._precision = {}

    def known(self, phrase):
        return self.prefix_counts.get(phrase, 0) >= self.MIN_PRODUCTS

    def precision(self, phrase):
        """Share of products mentioning the phrase in their title that are that brand."""
        if phrase not in self._precision:
            token_sets = [self.title_tokens.get(token, set()) for token in phrase.split()]
            mentions = len(set.intersection(*token_sets)) if token_sets else 0
            self._precision[phrase] = self.prefix_counts[phrase] / max(mentions, self.prefix_counts[phrase])
        return self._precision[phrase]

    def find(self, text):
        """Return (brand filter or None, text with any cue word removed)."""
        words = re.findall(r"[a-z0-9]+", text.lower())
        # 1. Signalled brands: "by sony", "from the north face", "nike brand".
        for match in BRAND_CUE.finditer(text):
            following = re.findall(r"[a-z0-9]+", text[match.end():].lower())
            for size in (3, 2, 1):
                phrase = " ".join(following[:size])
                if len(following) >= size and self.known(phrase):
                    remaining = (text[:match.start()] + text[match.end():]).strip()
                    return self._result(phrase), re.sub(r"\s+", " ", remaining)
        trailing = re.search(r"\b([a-z0-9]+(?:\s+[a-z0-9]+){0,2})\s+brand\b", text, re.I)
        if trailing:
            candidate = trailing.group(1).lower().split()
            for size in (3, 2, 1):
                phrase = " ".join(candidate[-size:])
                if len(candidate) >= size and self.known(phrase):
                    remaining = (text[:trailing.end() - len("brand")] + text[trailing.end():]).strip()
                    return self._result(phrase), re.sub(r"\s+", " ", remaining)
        # 2. Unprompted brand words the catalog uses almost only as a brand.
        # Accessory and compatibility searches ("breville replacement rack",
        # "case for samsung") name a brand the product only fits, so skip them.
        if set(words) & ACCESSORY_WORDS:
            return None, text
        for size in (3, 2, 1):
            for start in range(len(words) - size + 1):
                phrase = " ".join(words[start:start + size])
                if start > 0 and words[start - 1] in {"for", "fits", "with"}:
                    continue
                # Only complete brand names count here, so "under" (the start of
                # "under armour") or "the" never becomes a brand on its own.
                if (len(phrase) >= 2 and self.full_counts[phrase] >= self.MIN_PRODUCTS
                        and self.precision(phrase) >= self.MIN_PRECISION):
                    return self._result(phrase), text
        return None, text

    def _result(self, phrase):
        return {"value": phrase, "label": self.display.get(phrase, phrase.title())}


def has_brand(product, brand):
    """The product's brand starts with the brand words, or its title names the brand."""
    own = normalize_brand(product.get("brand"))
    if own:
        return own == brand or own.startswith(brand + " ")
    title = " ".join(re.findall(r"[a-z0-9]+", str(product.get("title", "")).lower()))
    return f" {brand} " in f" {title} "


# ------------------------------------------------------------------ all together

FILTER_TYPES = ("price", "brand", "color")


def parse_query(query, brands=None, skip=()):
    """Split a query into search text and the filters it asks for.

    `skip` lists filter types the shopper turned off; their words stay in the
    search text as typed.
    """
    text = re.sub(r"\s+", " ", query or "").strip()
    filters = {}
    if "price" not in skip:
        price, without_price = parse_price(text)
        # Never leave nothing to search for: "under $50" alone keeps its text.
        if price and re.search(r"[a-z]", without_price, re.I):
            filters["price"], text = price, without_price
    if brands is not None and "brand" not in skip:
        brand, text = brands.find(text)
        if brand:
            filters["brand"] = brand
    if "color" not in skip:
        color = parse_color(text)
        if color:
            filters["color"] = color
    return {"text": text, "filters": filters}


def price_label(price):
    symbol = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£"}.get(price.get("currency"), "")

    def amount(value):
        return f"{symbol}{value:,.0f}" if value == int(value) else f"{symbol}{value:,.2f}"

    if price["min"] is not None and price["max"] is not None:
        return f"{amount(price['min'])} – {amount(price['max'])}"
    if price["max"] is not None:
        return f"Under {amount(price['max'])}"
    return f"Over {amount(price['min'])}"


def describe(filters):
    """Chips for the page: what was understood, in the shopper's words."""
    chips = []
    if "price" in filters:
        chips.append({"type": "price", "label": price_label(filters["price"])})
    if "brand" in filters:
        chips.append({"type": "brand", "label": filters["brand"]["label"]})
    if "color" in filters:
        chips.append({"type": "color", "label": filters["color"]["value"].capitalize()})
    return chips

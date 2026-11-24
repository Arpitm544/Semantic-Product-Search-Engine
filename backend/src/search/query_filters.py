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


def _without(text, start, end):
    """Remove text[start:end] and tidy the spaces left behind."""
    return re.sub(r"\s+", " ", (text[:start] + " " + text[end:]).strip())


def _range_price(match):
    # A bare "1-2" or "2 to 4" is often a size or count ("2 to 4 years").
    # Ranges need a currency or the word "between" to count as prices.
    currencies = {_currency(match, "a"), _currency(match, "b")} - {None}
    if not currencies and not match.group(0).lower().startswith("between"):
        return None
    low, high = sorted((_amount(match.group("anum")), _amount(match.group("bnum"))))
    return {"min": low, "max": high, "currency": currencies.pop() if len(currencies) == 1 else None}


def _price_from_match(kind, match):
    """Turn one pattern match into a price filter, or None when it is not a price."""
    if kind == "range":
        return _range_price(match)
    amount = _amount(match.group("anum"))
    return {"min": amount if kind == "min" else None,
            "max": amount if kind == "max" else None,
            "currency": _currency(match, "a")}


def _price_matches(text):
    """Candidate price phrases in priority order, skipping sizes and counts."""
    for kind, pattern in PRICE_PATTERNS:
        for match in pattern.finditer(text):
            if _next_word(text, match.end()) not in UNITS:
                yield kind, match


def parse_price(text):
    """Return (price filter or None, text without the price phrase)."""
    for kind, match in _price_matches(text):
        price = _price_from_match(kind, match)
        if price:
            price["text"] = match.group(0).strip()
            return price, _without(text, match.start(), match.end())
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


TRAILING_BRAND = re.compile(r"\b([a-z0-9]+(?:\s+[a-z0-9]+){0,2})\s+brand\b", re.I)
COMPATIBILITY_WORDS = {"for", "fits", "with"}


def _words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def _phrases(words):
    """Runs of three, two, then one word, skipping those after "for", "fits" or "with"."""
    for size in (3, 2, 1):
        for start in range(len(words) - size + 1):
            if start == 0 or words[start - 1] not in COMPATIBILITY_WORDS:
                yield " ".join(words[start:start + size])


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
        for finder in (self._after_cue, self._before_brand_word, self._unprompted):
            found = finder(text)
            if found:
                return found
        return None, text

    def _longest_known(self, words, from_end=False):
        """The longest known brand among the first (or last) one to three words."""
        for size in (3, 2, 1):
            if len(words) < size:
                continue
            phrase = " ".join(words[-size:] if from_end else words[:size])
            if self.known(phrase):
                return phrase
        return None

    def _after_cue(self, text):
        """Signalled brands: "by sony", "from the north face"."""
        for match in BRAND_CUE.finditer(text):
            phrase = self._longest_known(_words(text[match.end():]))
            if phrase:
                return self._result(phrase), _without(text, match.start(), match.end())
        return None

    def _before_brand_word(self, text):
        """Signalled brands: "nike brand shoes"."""
        trailing = TRAILING_BRAND.search(text)
        phrase = self._longest_known(trailing.group(1).lower().split(), from_end=True) if trailing else None
        if not phrase:
            return None
        return self._result(phrase), _without(text, trailing.end() - len("brand"), trailing.end())

    def _unprompted(self, text):
        """Brand words the catalog uses almost only as a brand.

        Accessory and compatibility searches ("breville replacement rack",
        "case for samsung") name a brand the product only fits, so skip them."""
        words = _words(text)
        if set(words) & ACCESSORY_WORDS:
            return None
        for phrase in _phrases(words):
            if self._reliable(phrase):
                return self._result(phrase), text
        return None

    def _reliable(self, phrase):
        """Only complete brand names count, so "under" (the start of "under
        armour") or "the" never becomes a brand on its own."""
        complete = len(phrase) >= 2 and self.full_counts[phrase] >= self.MIN_PRODUCTS
        return complete and self.precision(phrase) >= self.MIN_PRECISION

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


def _price_step(text, _brands):
    price, without_price = parse_price(text)
    # Never leave nothing to search for: "under $50" alone keeps its text.
    if price and re.search(r"[a-z]", without_price, re.I):
        return price, without_price
    return None, text


def _brand_step(text, brands):
    return brands.find(text) if brands is not None else (None, text)


def _color_step(text, _brands):
    return parse_color(text), text


PARSE_STEPS = (("price", _price_step), ("brand", _brand_step), ("color", _color_step))


def parse_query(query, brands=None, skip=()):
    """Split a query into search text and the filters it asks for.

    `skip` lists filter types the shopper turned off; their words stay in the
    search text as typed.
    """
    text = re.sub(r"\s+", " ", query or "").strip()
    filters = {}
    for kind, step in PARSE_STEPS:
        if kind in skip:
            continue
        value, text = step(text, brands)
        if value:
            filters[kind] = value
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

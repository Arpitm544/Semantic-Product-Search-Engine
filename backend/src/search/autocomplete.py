"""Search suggestions while the shopper types, built from the product catalog.

Suggestions are common phrases (one to three words) from product titles and
brand names, ranked by how many products use them. Only catalog data is used,
so no shopper's searches are ever suggested to someone else.

    "wireless he"  -> "wireless headphones", "wireless headset", ...
    "headphn"      -> "headphones ..." (one typo is tolerated in a word being typed)
"""
from bisect import bisect_left
from collections import Counter, defaultdict
from heapq import nlargest
import re

from src.search.typos import STOP_WORDS, edit_distance

WORD = re.compile(r"[a-z0-9]+")
MAX_WORDS = 3
MIN_PRODUCTS = 3        # a phrase must appear in at least this many products
MIN_BRAND_PRODUCTS = 5
SHORT_PREFIX = 3        # prefixes this short use precomputed top lists
TOP_PER_PREFIX = 40
PLACEHOLDER_BRANDS = {"generic", "unknown", "unbranded", "na", "none", "no brand"}


def normalize(text):
    """Lowercase words separated by single spaces; keeps a trailing space."""
    words = " ".join(WORD.findall(str(text or "").lower()))
    return words + " " if words and str(text).endswith(" ") else words


def _good_phrase(words):
    """Phrases start with a letter and do not start or end with filler words."""
    first, last = words[0], words[-1]
    if not first[0].isalpha() or first in STOP_WORDS or last in STOP_WORDS:
        return False
    return all(len(word) > 1 or word.isdigit() for word in words)


def _title_phrases(title):
    words = WORD.findall(str(title or "").lower())
    phrases = set()
    for start in range(len(words)):
        for size in range(1, min(MAX_WORDS, len(words) - start) + 1):
            chunk = words[start:start + size]
            if _good_phrase(chunk):
                phrases.add(" ".join(chunk))
    return phrases


def _same_brand(one, other):
    """"samsung" and "samsung electronics" name the same brand."""
    return one.startswith(other + " ") or other.startswith(one + " ")


def _keep_shortest(chosen, brand):
    """Add a brand unless a shorter name for it is already chosen; replace longer names."""
    related = [other for other in chosen if _same_brand(brand, other)]
    if any(len(other) < len(brand) for other in related):
        return chosen
    return [other for other in chosen if other not in related] + [brand]


def _catalog_counts(products):
    phrase_counts = Counter()
    brand_counts = Counter()
    brand_names = {}
    for product in products:
        phrase_counts.update(_title_phrases(product.get("title")))
        brand = normalize(product.get("brand"))
        if brand and brand not in PLACEHOLDER_BRANDS:
            brand_counts[brand] += 1
            brand_names.setdefault(brand, str(product["brand"]).strip())
    return phrase_counts, brand_counts, brand_names


def _frequent(counts, minimum):
    return {phrase: count for phrase, count in counts.items() if count >= minimum}


def _typo_words(phrases):
    words_by_start = defaultdict(list)
    for phrase in phrases:
        if " " not in phrase and len(phrase) >= 4:
            words_by_start[phrase[:2]].append(phrase)
    return words_by_start


def _one_typo_away(fragment, word):
    sizes = range(max(3, len(fragment) - 1), len(fragment) + 2)
    return any(edit_distance(fragment, word[:size]) <= 1 for size in sizes)


class SortedPrefixIndex:
    """Phrases with counts, searchable by prefix."""

    def __init__(self, counts):
        self.counts = counts
        self.sorted = sorted(counts)
        tops = defaultdict(list)
        for phrase, count in counts.items():
            for size in range(1, min(SHORT_PREFIX, len(phrase)) + 1):
                tops[phrase[:size]].append((count, phrase))
        self.top = {prefix: [phrase for _, phrase in nlargest(TOP_PER_PREFIX, items, key=lambda item: (item[0], -len(item[1])))]
                    for prefix, items in tops.items()}

    def starting_with(self, prefix, limit):
        """Most common phrases that start with the prefix."""
        if len(prefix) <= SHORT_PREFIX:
            return self.top.get(prefix, [])[:limit]
        start = bisect_left(self.sorted, prefix)
        end = bisect_left(self.sorted, prefix + "￿")
        return nlargest(limit, self.sorted[start:end], key=lambda phrase: (self.counts[phrase], -len(phrase)))


class Autocomplete:
    """Prefix suggestions over catalog title phrases and brand names."""

    def __init__(self, products):
        phrase_counts, brand_counts, self.brand_names = _catalog_counts(products)
        self.phrases = SortedPrefixIndex(_frequent(phrase_counts, MIN_PRODUCTS))
        self.brands = SortedPrefixIndex(_frequent(brand_counts, MIN_BRAND_PRODUCTS))
        # Single words grouped by their first two letters, for typo-tolerant prefixes.
        self.words_by_start = _typo_words(self.phrases.counts)

    def brand_matches(self, typed, limit=2):
        prefix = normalize(typed).strip()
        if len(prefix) < 2:
            return []
        chosen = []
        for brand in self.brands.starting_with(prefix, limit * 4):
            if brand != prefix:
                chosen = _keep_shortest(chosen, brand)
        return [self.brand_names[brand] for brand in chosen[:limit]]

    def complete(self, typed, limit=8):
        """Whole-query suggestions for what has been typed so far.

        The last words typed are matched together as one phrase, longest
        context first, so "lego st" finds "lego star wars" rather than
        unrelated words that merely start with "st". A one-word context is
        used only when longer ones find nothing."""
        text = normalize(typed)
        typed_query = text.strip()
        if len(typed_query) < 2 or limit <= 0:
            return []
        words = text.split()
        typing = self._still_typing(text, words)
        found = self._context_completions(words, typing, limit)
        if typing and not found:
            found = self._typo_suggestions(words, limit)
        return [suggestion for suggestion in found if suggestion != typed_query]

    def _context_completions(self, words, typing, limit):
        for size in range(min(MAX_WORDS, len(words)), 0, -1):
            matches = self._with_context(words, size, typing, limit)
            if matches:
                return matches[:limit]
        return []

    def _typo_suggestions(self, words, limit):
        fragment = words[-1]
        if len(fragment) < 4:
            return []
        return [" ".join(words[:-1] + [word]) for word in self.typo_completions(fragment, limit)]

    @staticmethod
    def _still_typing(text, words):
        """False after a space or a finished filler word ("case for"): suggest the next word."""
        return not text.endswith(" ") and not (len(words) > 1 and words[-1] in STOP_WORDS)

    def _with_context(self, words, size, typing, limit):
        """Complete the last `size` words as one catalog phrase, keeping the words before them."""
        before, context = words[:-size], " ".join(words[-size:]) + ("" if typing else " ")
        matches = [phrase for phrase in self.phrases.starting_with(context, limit * 2) if phrase != context.strip()]
        return [" ".join(before + [phrase]) for phrase in matches]

    def typo_completions(self, fragment, limit):
        """Common words whose start is one typo away from the fragment."""
        words = self.words_by_start.get(fragment[:2], [])
        candidates = (word for word in words if _one_typo_away(fragment, word))
        return nlargest(limit, candidates, key=lambda word: (self.phrases.counts[word], -len(word)))

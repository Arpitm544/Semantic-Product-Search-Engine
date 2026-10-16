"""Find cautious spelling corrections using words from the product catalog."""

import re
from functools import lru_cache

try:
    from rapidfuzz.distance import OSA
except ImportError:
    OSA = None

WORD_PATTERN = re.compile(r"\b\w+\b")
STOP_WORDS = frozenset(
    "a an and are as at be by for from how i in is it me my of on or our "
    "please that the their this to want was we what when where which who "
    "why will with you your find show looking need some like".split()
)


def edit_distance(left, right):
    """OSA distance: insert, delete, substitute, or swap adjacent letters."""
    if OSA is not None:
        return OSA.distance(left, right)
    # Each cell records the fewest edits needed to match two word prefixes.
    matrix = [[0] * (len(right) + 1) for _ in range(len(left) + 1)]
    for i in range(len(left) + 1):
        matrix[i][0] = i
    for j in range(len(right) + 1):
        matrix[0][j] = j
    for i in range(1, len(left) + 1):
        for j in range(1, len(right) + 1):
            matrix[i][j] = min(
                matrix[i - 1][j] + 1,
                matrix[i][j - 1] + 1,
                matrix[i - 1][j - 1] + (left[i - 1] != right[j - 1]),
            )
            if (i > 1 and j > 1 and left[i - 1] == right[j - 2]
                    and left[i - 2] == right[j - 1]):
                matrix[i][j] = min(matrix[i][j], matrix[i - 2][j - 2] + 1)
    return matrix[-1][-1]


class CatalogSpelling:
    """Suggest corrections only when the catalog provides a clear match."""

    def __init__(self, vocabulary):
        self.vocabulary = frozenset(vocabulary)
        self.by_length = {}
        for word in sorted(self.vocabulary):
            if word.isalpha() and word.isascii() and word not in STOP_WORDS:
                self.by_length.setdefault(len(word), []).append(word)

    def should_keep_word(self, word):
        """Leave known words, common words, numbers, and non-English text alone."""
        return (
            word in self.vocabulary
            or word in STOP_WORDS
            or not 4 <= len(word) <= 40
            or not word.isalpha()
            or not word.isascii()
        )

    def find_similar_words(self, word, max_edits):
        """Find catalog words close in both length and spelling."""
        candidates = []
        for length in range(len(word) - max_edits, len(word) + max_edits + 1):
            for candidate in self.by_length.get(length, []):
                distance = edit_distance(word, candidate)
                similarity = 1 - distance / max(len(word), length)
                if distance <= max_edits and similarity >= 0.8:
                    candidates.append((distance, candidate))
        return candidates

    @lru_cache(maxsize=8192)
    def suggestion(self, word):
        """Return (replacement, edit count), or None if no clear correction exists."""
        word = word.lower()
        if self.should_keep_word(word):
            return None

        max_edits = 1 if len(word) < 8 else 2
        candidates = sorted(self.find_similar_words(word, max_edits))
        if not candidates:
            return None

        # Two equally close words are ambiguous, so avoid guessing.
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            return None
        distance, replacement = candidates[0]
        return replacement, distance

    def correct(self, query):
        """Correct individual words while preserving spaces and punctuation."""
        corrections = []

        def replace_word(match):
            original = match.group()
            suggestion = self.suggestion(original)
            if suggestion is None:
                return original
            replacement, distance = suggestion
            corrections.append({
                "original": original,
                "suggestion": replacement,
                "distance": distance,
            })
            return replacement

        corrected_query = WORD_PATTERN.sub(replace_word, query)
        return corrected_query, corrections


class FrequencySpelling(CatalogSpelling):
    """Use product word counts to choose between equally close corrections."""

    def __init__(self, frequency):
        super().__init__(frequency)
        self.frequency = frequency

    @lru_cache(maxsize=8192)
    def suggestion(self, word):
        word = word.lower()
        if self.should_keep_word(word):
            return None

        max_edits = 1 if len(word) < 8 else 2
        candidates = self.find_similar_words(word, max_edits)
        if not candidates:
            return None

        closest_distance = min(distance for distance, candidate in candidates)
        closest_words = [
            candidate for distance, candidate in candidates
            if distance == closest_distance
        ]
        closest_words.sort(key=lambda candidate: (-self.frequency[candidate], candidate))

        # An ambiguous correction needs a clearly more common winner.
        if len(closest_words) > 1:
            most_common_count = self.frequency[closest_words[0]]
            second_count = self.frequency[closest_words[1]]
            if most_common_count < 5 or most_common_count < 3 * max(1, second_count):
                return None
        return closest_words[0], closest_distance

    def common_alternatives(self, word):
        """Find up to two common catalog words that differ by one edit."""
        candidates = []
        for distance, candidate in self.find_similar_words(word, max_edits=1):
            count = self.frequency[candidate]
            if candidate != word and count >= 5 and distance == 1:
                candidates.append((count, candidate))
        candidates.sort(key=lambda item: (-item[0], item[1]))
        return [candidate for count, candidate in candidates[:2]]

    def alternatives(self, query, maximum=5):
        """Try the original query, its correction, and common spelling variations."""
        corrected_query, _ = self.correct(query)
        variations = list(dict.fromkeys([query, corrected_query]))
        for match in re.finditer(r"\b[a-zA-Z]+\b", query):
            word = match.group().lower()
            if word in STOP_WORDS or not 4 <= len(word) <= 40 or self.frequency[word] >= 5:
                continue
            for replacement in self.common_alternatives(word):
                variation = query[:match.start()] + replacement + query[match.end():]
                if variation not in variations:
                    variations.append(variation)
                if len(variations) >= maximum:
                    return variations
        return variations

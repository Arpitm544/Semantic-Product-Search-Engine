"""Conservative catalog spelling suggestions with adjacent transpositions."""

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
    def __init__(self, vocabulary):
        self.vocabulary = frozenset(vocabulary)
        self.by_length = {}
        for word in sorted(self.vocabulary):
            if word.isalpha() and word.isascii() and word not in STOP_WORDS:
                self.by_length.setdefault(len(word), []).append(word)

    @lru_cache(maxsize=8192)
    def suggestion(self, word):
        word = word.lower()
        # Keep known words, short terms, model numbers, and non-Latin text.
        if (word in self.vocabulary or word in STOP_WORDS or len(word) < 4
                or len(word) > 40 or not word.isalpha() or not word.isascii()):
            return None
        max_edits = 1 if len(word) < 8 else 2
        candidates = []
        for length in range(len(word) - max_edits, len(word) + max_edits + 1):
            for candidate in self.by_length.get(length, []):
                distance = edit_distance(word, candidate)
                threshold = 0.75 if len(word) == length == 4 else 0.8
                if distance <= max_edits and 1 - distance / max(len(word), length) >= threshold:
                    candidates.append((distance, candidate))
        if not candidates:
            return None
        candidates.sort()
        # An equally close alternative is ambiguous: let semantic search help.
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            return None
        return candidates[0][1], candidates[0][0]

    def correct(self, query):
        corrections = []

        def replace(match):
            original = match.group()
            suggestion = self.suggestion(original)
            if suggestion is None:
                return original
            replacement, distance = suggestion
            corrections.append({
                "original": original, "suggestion": replacement, "distance": distance,
            })
            return replacement

        corrected = WORD_PATTERN.sub(replace, query)
        return corrected, corrections


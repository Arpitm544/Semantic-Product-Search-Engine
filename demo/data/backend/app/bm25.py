import math
import re
import pickle
import os
from typing import List, Dict, Any, Tuple

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "if", "in", 
    "into", "is", "it", "no", "not", "of", "on", "or", "such", "that", "the", 
    "their", "then", "there", "these", "they", "this", "to", "was", "will", "with"
}

def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric terms excluding stopwords."""
    if not text:
        return []
    words = re.findall(r'\b[a-zA-Z0-9]+\b', text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]

class BM25Okapi:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_len = []
        self.avgdl = 0.0
        self.doc_freqs = []
        self.idf = {}
        self.doc_count = 0
        self.products = []

    def fit(self, products: List[Dict[str, Any]]):
        self.products = products
        self.doc_count = len(products)
        self.doc_len = []
        self.doc_freqs = []
        df_counts = {}

        corpus_tokens = []
        for prod in products:
            text = (
                f"{prod.get('title', '')} "
                f"{prod.get('category', '')} "
                f"{prod.get('description', '')} "
                f"{' '.join(prod.get('attributes', []))}"
            )
            tokens = tokenize(text)
            corpus_tokens.append(tokens)
            self.doc_len.append(len(tokens))

            # Term frequency dict for this doc
            freq_dict = {}
            for token in tokens:
                freq_dict[token] = freq_dict.get(token, 0) + 1
            self.doc_freqs.append(freq_dict)

            # Update document frequency
            for token in set(tokens):
                df_counts[token] = df_counts.get(token, 0) + 1

        self.avgdl = sum(self.doc_len) / self.doc_count if self.doc_count > 0 else 0.0

        # Calculate Inverse Document Frequency (IDF)
        for token, df in df_counts.items():
            # Standard Lucene/BM25 IDF formula
            idf_val = math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1.0)
            self.idf[token] = max(idf_val, 0.01)

    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """Search query and return ranked list of (doc_index, score)."""
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scores = [0.0] * self.doc_count

        for q_token in query_tokens:
            if q_token not in self.idf:
                continue
            idf_val = self.idf[q_token]

            for doc_idx, freq_dict in enumerate(self.doc_freqs):
                tf = freq_dict.get(q_token, 0)
                if tf == 0:
                    continue

                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (self.doc_len[doc_idx] / self.avgdl))
                scores[doc_idx] += idf_val * (numerator / denominator)

        # Pair with doc index and sort
        ranked = [(idx, score) for idx, score in enumerate(scores) if score > 0.0]
        ranked.sort(key=lambda x: x[1], reverse=True)

        return ranked[:top_k]

    def save(self, filepath: str):
        with open(filepath, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, filepath: str) -> "BM25Okapi":
        with open(filepath, "rb") as f:
            return pickle.load(f)

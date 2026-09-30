"""
BM25Okapi Information Retrieval baseline implementation.
Addresses TR-003 / BR-004: Keyword-search baseline over preprocessed catalog.
"""
import math
import pickle
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config import BM25_INDEX_PATH, PROCESSED_DATA_PATH
from src.data.load_data import load_cleaned_products


def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric tokens."""
    return re.findall(r"\b\w+\b", (text or "").lower())


class BM25Okapi:
    """
    BM25Okapi retrieval model implementation.
    Parameters:
        k1: Term frequency saturation parameter (default: 1.5)
        b: Document length normalization parameter (default: 0.75)
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avgdl = 0.0
        self.doc_freqs: List[Dict[str, int]] = []
        self.idf: Dict[str, float] = {}
        self.doc_len: List[int] = []
        self.products: List[Dict[str, Any]] = []

    def fit(self, products: List[Dict[str, Any]]) -> "BM25Okapi":
        """Index the products using their canonical representation text."""
        self.products = products
        self.corpus_size = len(products)
        self.doc_len = []
        self.doc_freqs = []

        df_counts: Dict[str, int] = {}

        for p in products:
            text = p.get("representation_text") or f"{p.get('title', '')} {p.get('description', '')}"
            tokens = tokenize(text)
            self.doc_len.append(len(tokens))

            frequencies: Dict[str, int] = {}
            for token in tokens:
                frequencies[token] = frequencies.get(token, 0) + 1
            self.doc_freqs.append(frequencies)

            for token in frequencies.keys():
                df_counts[token] = df_counts.get(token, 0) + 1

        self.avgdl = sum(self.doc_len) / self.corpus_size if self.corpus_size > 0 else 0.0

        # Compute Robertson-Spärck Jones IDF with smoothing
        self.idf = {}
        for token, freq in df_counts.items():
            self.idf[token] = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)

        return self

    def get_scores(self, query: str) -> List[float]:
        """Compute BM25 relevance scores for all documents given a query."""
        tokens = tokenize(query)
        scores = [0.0] * self.corpus_size

        for token in tokens:
            if token not in self.idf:
                continue
            idf = self.idf[token]
            for idx in range(self.corpus_size):
                tf = self.doc_freqs[idx].get(token, 0)
                if tf > 0:
                    numerator = tf * (self.k1 + 1.0)
                    denominator = tf + self.k1 * (1.0 - self.b + self.b * (self.doc_len[idx] / self.avgdl))
                    scores[idx] += idf * (numerator / denominator)

        return scores

    def search(self, query: str, top_k: int = 10) -> List[Tuple[Dict[str, Any], float]]:
        """Search products and return top_k (product, score) pairs."""
        scores = self.get_scores(query)
        scored_indices = sorted(
            [(idx, score) for idx, score in enumerate(scores) if score > 0.0],
            key=lambda x: x[1],
            reverse=True,
        )

        results = []
        for idx, score in scored_indices[:top_k]:
            results.append((self.products[idx], score))
        return results

    def save(self, path: Optional[Path] = None) -> Path:
        """Serialize BM25 index to disk."""
        target_path = path or BM25_INDEX_PATH
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "wb") as f:
            pickle.dump(self, f)
        print(f"BM25 index saved to {target_path}")
        return target_path

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "BM25Okapi":
        """Load serialized BM25 index from disk."""
        target_path = path or BM25_INDEX_PATH
        if not target_path.exists():
            raise FileNotFoundError(f"BM25 index not found at {target_path}")
        with open(target_path, "rb") as f:
            return pickle.load(f)


def main():
    products = load_cleaned_products()
    bm25 = BM25Okapi()
    bm25.fit(products)
    bm25.save(BM25_INDEX_PATH)

    # Test sample search
    sample_query = "warm winter jacket"
    results = bm25.search(sample_query, top_k=3)
    print(f"\nQuery: '{sample_query}'")
    for prod, score in results:
        print(f"- [Score: {score:.2f}] {prod['title']} ({prod['category']})")


if __name__ == "__main__":
    main()

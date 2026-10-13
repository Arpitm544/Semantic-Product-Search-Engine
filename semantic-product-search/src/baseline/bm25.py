"""Simple keyword search over the processed product catalog."""
from collections import Counter
import math
import pickle
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config import BM25_INDEX_PATH
from src.data.load_data import load_cleaned_products


def tokenize(text: str) -> List[str]:
    """Turn text into lowercase words."""
    return re.findall(r"\b\w+\b", (text or "").lower())


def fit_bm25(products: List[Dict[str, Any]], k1: float = 1.5) -> Dict[str, Any]:
    """Build a BM25 index from products."""
    word_counts = [
        Counter(tokenize(product.get("representation_text") or
                         f"{product.get('title', '')} {product.get('description', '')}"))
        for product in products
    ]
    doc_frequency = Counter(word for counts in word_counts for word in counts)
    total_products = len(products)
    idf = {
        word: math.log((total_products - count + 0.5) / (count + 0.5) + 1)
        for word, count in doc_frequency.items()
    }
    return {"products": products, "word_counts": word_counts, "idf": idf, "k1": k1}


def search_bm25(
    index: Dict[str, Any], query: str, top_k: int = 10
) -> List[Tuple[Dict[str, Any], float]]:
    """Return the best matching products and their scores."""
    query_words = tokenize(query)
    scores = []

    for counts in index["word_counts"]:
        score = 0.0
        for word in query_words:
            frequency = counts.get(word, 0)
            if frequency:
                k1 = index["k1"]
                score += index["idf"][word] * frequency * (k1 + 1) / (frequency + k1)
        scores.append(score)

    ranked = sorted(
        ((i, score) for i, score in enumerate(scores) if score > 0),
        key=lambda result: result[1],
        reverse=True,
    )
    return [(index["products"][i], score) for i, score in ranked[:top_k]]


def save_bm25(index: Dict[str, Any], path: Optional[Path] = None) -> Path:
    """Save the index to a file."""
    path = path or BM25_INDEX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as file:
        pickle.dump(index, file)
    print(f"BM25 index saved to {path}")
    return path


def load_bm25(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load an index from a file."""
    with open(path or BM25_INDEX_PATH, "rb") as file:
        return pickle.load(file)


def main() -> None:
    index = fit_bm25(load_cleaned_products())
    save_bm25(index)

    query = "warm winter jacket"
    print(f"\nQuery: '{query}'")
    for product, score in search_bm25(index, query, top_k=3):
        print(f"- [Score: {score:.2f}] {product['title']} ({product['category']})")


if __name__ == "__main__":
    main()

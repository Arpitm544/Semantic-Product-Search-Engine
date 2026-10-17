"""Simple keyword search over the processed product catalog."""
from collections import Counter
import math
import pickle
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config import BM25_INDEX_PATH


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
    postings = {}
    for index, counts in enumerate(word_counts):
        for word, frequency in counts.items():
            postings.setdefault(word, []).append((index, frequency))
    return {"products": products, "word_counts": word_counts, "idf": idf,
            "postings": postings, "k1": k1}


def search_bm25(
    index: Dict[str, Any], query: str, top_k: int = 10
) -> List[Tuple[Dict[str, Any], float]]:
    """Return the best matching products and their scores."""
    query_words = tokenize(query)
    if "postings" not in index:
        # Saved indexes from earlier versions can still be used.
        index["postings"] = {}
        for i, counts in enumerate(index["word_counts"]):
            for word, frequency in counts.items():
                index["postings"].setdefault(word, []).append((i, frequency))
    scores = {}
    k1 = index["k1"]
    for word in query_words:
        for i, frequency in index["postings"].get(word, []):
            scores[i] = scores.get(i, 0.0) + (
                index["idf"][word] * frequency * (k1 + 1) / (frequency + k1)
            )
    ranked = sorted(scores.items(), key=lambda result: (-result[1], result[0]))
    return [(index["products"][i], score) for i, score in ranked[:max(0, top_k)]]


def save_bm25(index: Dict[str, Any], path: Optional[Path] = None) -> Path:
    """Save the index to a file."""
    path = path or BM25_INDEX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as file:
        pickle.dump(index, file)
    print(f"BM25 index saved to {path}")
    return path


def main() -> None:
    from src.data.catalog import load_products

    index = fit_bm25(load_products())
    save_bm25(index)

    query = "warm winter jacket"
    print(f"\nQuery: '{query}'")
    for product, score in search_bm25(index, query, top_k=3):
        print(f"- [Score: {score:.2f}] {product['title']} ({product['category']})")


if __name__ == "__main__":
    main()

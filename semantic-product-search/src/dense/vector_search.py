"""
Dense Vector Search Engine using Sentence-Transformers (SBERT) and FAISS index.
Provides semantic vector indexing and retrieval for product catalog records.
"""
import pickle
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from src.config import (
    FAISS_INDEX_PATH,
    FAISS_ID_MAP_PATH,
    EMBEDDING_MODEL_NAME,
)
from src.data.load_data import load_cleaned_products

logger = logging.getLogger(__name__)


class DenseVectorSearch:
    """
    Dense Vector Search engine using SentenceTransformers embeddings and FAISS index.
    """

    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME):
        self.model_name = model_name
        self._model: Optional[SentenceTransformer] = None
        self.index: Optional[faiss.IndexFlatIP] = None
        self.products: List[Dict[str, Any]] = []
        self.dimension: Optional[int] = None

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load SentenceTransformer model."""
        if self._model is None:
            logger.info(f"Loading SentenceTransformer model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _normalize_embeddings(self, embeddings: np.ndarray) -> np.ndarray:
        """Normalizes vector embeddings to unit length for Cosine Similarity via Inner Product."""
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1e-10
        return (embeddings / norms).astype(np.float32)

    def fit(self, products: List[Dict[str, Any]]) -> "DenseVectorSearch":
        """
        Extracts representation text from products, generates SBERT embeddings,
        normalizes them, and builds a FAISS IndexFlatIP index.
        """
        if not products:
            raise ValueError("Cannot fit DenseVectorSearch on empty product catalog.")

        self.products = products
        texts = [p.get("representation_text", p.get("title", "")) for p in products]

        logger.info(f"Generating embeddings for {len(texts)} products using {self.model_name}...")
        raw_embeddings = self.model.encode(texts, show_progress_bar=False, batch_size=32)
        normalized_embeddings = self._normalize_embeddings(np.array(raw_embeddings))

        self.dimension = normalized_embeddings.shape[1]
        self.index = faiss.IndexFlatIP(self.dimension)
        self.index.add(normalized_embeddings)

        logger.info(f"Built FAISS index with {self.index.ntotal} vectors of dim {self.dimension}.")
        return self

    def search(self, query: str, top_k: int = 10) -> List[Tuple[Dict[str, Any], float]]:
        """
        Encodes query string, computes cosine similarity against indexed vectors,
        and returns top_k matching products along with similarity scores.
        """
        if self.index is None or not self.products:
            raise RuntimeError("Index is empty. Call fit() or load() before searching.")

        query_embedding = self.model.encode([query], show_progress_bar=False)
        query_normalized = self._normalize_embeddings(np.array(query_embedding))

        scores, indices = self.index.search(query_normalized, top_k)
        
        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx != -1 and idx < len(self.products):
                results.append((self.products[idx], float(score)))

        return results

    def save(
        self,
        index_path: Path = FAISS_INDEX_PATH,
        map_path: Path = FAISS_ID_MAP_PATH,
    ) -> None:
        """Saves serialized FAISS index and product metadata payload."""
        if self.index is None:
            raise RuntimeError("Cannot save empty index.")

        index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(index_path))

        with open(map_path, "wb") as f:
            pickle.dump(
                {
                    "products": self.products,
                    "model_name": self.model_name,
                    "dimension": self.dimension,
                },
                f,
            )
        logger.info(f"Saved FAISS index to {index_path} and product metadata to {map_path}")

    @classmethod
    def load(
        cls,
        index_path: Path = FAISS_INDEX_PATH,
        map_path: Path = FAISS_ID_MAP_PATH,
    ) -> "DenseVectorSearch":
        """Loads serialized FAISS index and product metadata payload."""
        if not index_path.exists() or not map_path.exists():
            raise FileNotFoundError(f"Index or metadata map file not found at {index_path} / {map_path}")

        with open(map_path, "rb") as f:
            meta = pickle.load(f)

        engine = cls(model_name=meta.get("model_name", EMBEDDING_MODEL_NAME))
        engine.products = meta["products"]
        engine.dimension = meta["dimension"]
        engine.index = faiss.read_index(str(index_path))

        logger.info(f"Loaded FAISS index from {index_path} with {engine.index.ntotal} records.")
        return engine


def main():
    print("Loading cleaned products from MongoDB...")
    products = load_cleaned_products()
    
    dense_engine = DenseVectorSearch()
    dense_engine.fit(products)
    dense_engine.save()

    test_query = "wireless Bluetooth headphones"
    print(f"\n--- Testing Dense Search Query: '{test_query}' ---")
    results = dense_engine.search(test_query, top_k=3)
    for prod, score in results:
        print(f"[{score:.4f}] ID {prod.get('id')}: {prod.get('title')}")


if __name__ == "__main__":
    main()

"""Build the search engine once and reuse it while the catalog stays the same."""

import hashlib
import os
import logging
import tempfile
from zipfile import BadZipFile
from pathlib import Path
from threading import Event, Lock

from src.config import PROJECT_ROOT
from src.data.catalog import load_products, version, CatalogUpdatingError
from src.search.product_search import ProductSearch
from api.ranking_service import get_candidate_ranker

_search_engine = None
_search_signature = None
_search_lock = Lock()
_search_ready = Event()
_search_error = None


def get_search_engine():
    """Publish readiness only after a catalog check or rebuild succeeds."""
    global _search_error
    with _search_lock:
        try:
            engine = build_search_engine()
        except Exception as error:
            _search_ready.clear()
            _search_error = None if isinstance(error, CatalogUpdatingError) else str(error)
            raise
        _search_error = None
        _search_ready.set()
        return engine


def build_search_engine():
    """Load products and models when needed, then return a ready search engine."""
    global _search_engine, _search_signature

    catalog_version = version()
    model_path = os.environ.get("SEMANTIC_MODEL_PATH", "models/colab-export/esci-minilm-20k")
    reranker_path = os.environ.get("RERANKER_MODEL_PATH", "models/ms-marco-MiniLM-L6-v2")

    # This identifies the catalog and model settings used by the engine.
    signature = (catalog_version["sha256"], catalog_version["updated_at"],
                 model_path, reranker_path)
    if _search_engine is not None and signature == _search_signature:
        return _search_engine

    _search_ready.clear()
    print("Loading catalog from MongoDB...", flush=True)
    products = load_products()
    if version() != catalog_version:
        raise CatalogUpdatingError("Catalog changed before index initialization.")
    semantic = load_semantic_search(products, model_path, catalog_version["sha256"])
    reranker = load_reranker(reranker_path)

    # ProductSearch combines spelling correction, retrieval, and ranking.
    _search_engine = ProductSearch(products, semantic, reranker, model_lock=get_candidate_ranker().lock)
    _search_signature = signature
    return _search_engine


def vector_cache_path(model_path, catalog_hash):
    """Choose a cache file for this catalog and this version of the model."""
    model_dir = Path(model_path)
    weights = sorted(path for pattern in ("*.safetensors", "pytorch_model*.bin", "*.index.json")
                     for path in model_dir.rglob(pattern))
    if not weights:
        raise FileNotFoundError(f"No supported checkpoint weights in {model_dir}")
    fingerprint = [(str(path.relative_to(model_dir)), path.stat().st_size,
                    path.stat().st_mtime_ns) for path in weights]
    cache_identity = catalog_hash + str(model_path) + repr(fingerprint)
    cache_key = hashlib.sha256(cache_identity.encode()).hexdigest()
    cache_dir = PROJECT_ROOT / "indexes" / "catalog"
    return cache_dir / (cache_key + ".npz")


def load_semantic_search(products, model_path, catalog_hash):
    """Load saved product vectors, or build and save them on the first run."""
    import torch
    import numpy as np
    from src.semantic.vector_search import SemanticVectorSearch

    torch.set_num_threads(2)
    model_path = str((PROJECT_ROOT / model_path).resolve())
    semantic = SemanticVectorSearch(model_path, local_files_only=True, device="cpu")
    ranker = get_candidate_ranker()
    semantic._model = ranker.encoder
    cache_path = vector_cache_path(model_path, catalog_hash)

    restored = False
    if cache_path.exists():
        try:
            restore_vectors(semantic, products, cache_path)
            restored = True
        except (OSError, ValueError, EOFError, BadZipFile):
            logging.getLogger(__name__).warning("Invalid vector cache; rebuilding.", exc_info=True)
    if not restored:
        print(f"Building vectors for {len(products):,} products on CPU. This may take several minutes.", flush=True)
        with ranker.lock:
            semantic.fit(products)
        vectors = semantic.index.reconstruct_n(0, len(products))
        product_ids = np.array([product["id"] for product in products])
        temporary = None
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=cache_path.parent, suffix=".npz", delete=False) as stream:
                temporary = Path(stream.name)
                np.savez_compressed(stream, ids=product_ids, vectors=vectors)
            temporary.replace(cache_path)
        except OSError:
            logging.getLogger(__name__).warning("Could not save vector cache; search remains available.", exc_info=True)
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    logging.getLogger(__name__).warning("Could not remove temporary vector cache.", exc_info=True)

    return semantic


def restore_vectors(semantic, products, cache_path):
    """Restore the vector index and check that it matches the loaded products."""
    import faiss
    import numpy as np

    print("Loading saved vector index...", flush=True)
    with np.load(cache_path, allow_pickle=False) as cached:
        product_ids = [product["id"] for product in products]
        if cached["ids"].tolist() != product_ids:
            raise ValueError("Cached vector IDs do not match MongoDB.")
        vectors = cached["vectors"]

    semantic.products = products
    semantic.dimension = vectors.shape[1]
    semantic.index = faiss.IndexFlatIP(semantic.dimension)
    semantic.index.add(vectors)


def load_reranker(model_path):
    """Reuse the same cross-encoder as Google Shopping candidate ranking."""
    return get_candidate_ranker().reranker

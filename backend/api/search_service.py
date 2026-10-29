"""Build the search engine once and reuse it while the catalog stays the same."""

import os
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
                 model_path, reranker_path,
                 os.getenv("ATLAS_VECTOR_INDEX", "product_vectors"))
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


def load_semantic_search(products, model_path, catalog_hash):
    """Load Atlas retrieval; embeddings and indexes are managed by the setup command."""
    from src.data.catalog import database
    from src.semantic.atlas_search import AtlasVectorSearch
    from src.semantic.identity import vector_generation

    resolved = str((PROJECT_ROOT / model_path).resolve())
    return AtlasVectorSearch(database(), products, get_candidate_ranker().encoder,
                             resolved, vector_generation(resolved, catalog_hash))


def load_reranker(model_path):
    """Reuse the same cross-encoder as Google Shopping candidate ranking."""
    return get_candidate_ranker().reranker

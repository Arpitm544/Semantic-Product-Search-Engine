"""Build the search engine once and reuse it while the catalog stays the same."""

import logging
import os
from threading import Event, Lock

from pymongo.errors import PyMongoError

from src.config import PROJECT_ROOT
from src.data.catalog import load_products, version, CatalogUpdatingError
from src.search.product_search import ProductSearch
from src.search.ranking import configured_pipeline_params
from src.search.relevance import configured_reranker_path
from api.ranking_service import get_candidate_ranker

logger = logging.getLogger(__name__)
# Decided by scripts/train_ltr.py results; see backend/ranking/ltr_report.json.
DEFAULT_RANKER = "blend"

_search_engine = None
_search_signature = None
_search_params = None
_search_lock = Lock()
_search_ready = Event()
_search_error = None


def get_search_engine():
    """Publish readiness only after a catalog check or rebuild succeeds."""
    global _search_error
    with _search_lock:
        try:
            engine = build_search_engine()
        except CatalogUpdatingError:
            if _search_engine is None:
                _search_ready.clear()
                _search_error = None
                raise
            # An import is in progress or the catalog changed mid-load. Keep
            # serving the last complete engine; the next request retries.
            _search_ready.set()
            return _search_engine
        except PyMongoError as error:
            if _search_engine is not None:
                logger.warning("Catalog refresh failed (%s); continuing with cached index.", type(error).__name__)
                _search_ready.set()
                _search_error = None
                return _search_engine
            _search_ready.clear()
            _search_error = str(error)
            raise
        except Exception as error:
            _search_ready.clear()
            _search_error = str(error)
            raise
        _search_error = None
        _search_ready.set()
        return engine


def build_search_engine():
    """Load products and models when needed, then return a ready search engine."""
    global _search_engine, _search_signature, _search_params

    catalog_version = version()
    model_path = os.environ.get("SEMANTIC_MODEL_PATH", "models/colab-export/esci-minilm-20k")
    reranker_path = configured_reranker_path()
    params = configured_pipeline_params()

    # This identifies the catalog and model settings used by the engine.
    signature = (catalog_version["sha256"], catalog_version["updated_at"],
                 model_path, reranker_path,
                 os.getenv("ATLAS_VECTOR_INDEX", "product_vectors"))
    if _search_engine is not None and signature == _search_signature and (
        _search_params is None or _search_params == params
    ):
        return _search_engine

    _search_ready.clear()
    print("Loading catalog from MongoDB...", flush=True)
    products = load_products()
    if version() != catalog_version:
        raise CatalogUpdatingError("Catalog changed before index initialization.")
    semantic = load_semantic_search(products, model_path, catalog_version["sha256"])
    reranker = load_reranker(reranker_path)

    # ProductSearch combines spelling correction, retrieval, and ranking.
    engine = ProductSearch(products, semantic, reranker,
                           model_lock=get_candidate_ranker().lock, params=params)
    engine.learned_ranker = load_learned_ranker(ranker_choice())
    _search_engine = engine
    _search_signature = signature
    _search_params = params
    return _search_engine


def ranker_choice():
    """SEARCH_RANKER=learned uses the LambdaMART model; anything else keeps the blend."""
    return "learned" if os.environ.get("SEARCH_RANKER", DEFAULT_RANKER).strip().lower() == "learned" else "blend"


def load_learned_ranker(choice):
    """The learned ranker, or None (the 25/75 blend) when off or unavailable."""
    if choice != "learned":
        return None
    try:
        from src.ranking.learned import LearnedRanker
        ranker = LearnedRanker.load()
    except (ImportError, OSError, ValueError) as error:
        # A missing model file or library must never stop search from starting.
        logger.warning("Learned ranker unavailable (%s); using the blend.", type(error).__name__)
        return None
    print("Using the learned ranker.", flush=True)
    return ranker


def load_semantic_search(products, model_path, catalog_hash):
    """Load Atlas retrieval; embeddings and indexes are managed by the setup command."""
    from src.data.catalog import database
    from src.semantic.atlas_search import AtlasVectorSearch
    from src.semantic.identity import vector_generation

    resolved = str((PROJECT_ROOT / model_path).resolve())
    ranker = get_candidate_ranker()
    return AtlasVectorSearch(database(), products, ranker.encoder, resolved,
                             vector_generation(resolved, catalog_hash), model_lock=ranker.lock)


def load_reranker(model_path):
    """Reuse the same cross-encoder as Google Shopping candidate ranking."""
    return get_candidate_ranker().reranker

"""Small local API server for Semantic Product Search."""

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import sys
from threading import Lock, Event, Thread
from urllib.parse import parse_qs, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env", override=False)

from src.config import EMBEDDING_MODEL_NAME
from src.search.amazon import AmazonSearch
from src.data.amazon_mongo import load_products, version, COLLECTION
from pymongo.errors import PyMongoError

DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
EVAL_PATH = DATA_DIR / "eval" / "eval_set.json"
BM25_REPORT_PATH = REPORTS_DIR / "baseline_metrics.json"
SEMANTIC_REPORT_PATH = REPORTS_DIR / "dense_metrics.json"
FRONTEND_ORIGINS = {
    origin.strip()
    for origin in os.environ.get(
        "FRONTEND_ORIGINS",
        "http://localhost:3001,http://127.0.0.1:3001",
    ).split(",")
    if origin.strip()
}
PORT = int(os.environ.get("PORT", "8000"))
_search_engine = None
_search_signature = None
_search_lock = Lock()
_search_ready = Event()
_search_error = None


def read_json(path, fallback=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def get_search_engine():
    """Index once per catalog version; serving never downloads a model."""
    global _search_engine, _search_signature
    with _search_lock:
        manifest = version()
        model_path = os.environ.get("SEMANTIC_MODEL_PATH", "models/colab-export/esci-minilm-20k")
        reranker_path = os.environ.get("RERANKER_MODEL_PATH", "models/ms-marco-MiniLM-L6-v2")
        signature = (manifest["sha256"], manifest["updated_at"], model_path, reranker_path)
        if _search_engine is not None and signature == _search_signature:
            return _search_engine
        print("Loading Amazon catalog from MongoDB...", flush=True)
        products = load_products()
        import torch
        from sentence_transformers import CrossEncoder
        from src.semantic.vector_search import SemanticVectorSearch
        torch.set_num_threads(2)
        model_name = str((PROJECT_ROOT / model_path).resolve())
        semantic = SemanticVectorSearch(model_name, local_files_only=True, device="cpu")
        # Persist only vectors and IDs; product records always come from MongoDB.
        import hashlib
        import numpy as np
        import faiss
        weights = Path(model_name) / "model.safetensors"
        cache_key = hashlib.sha256((manifest["sha256"] + model_name
                    + str(weights.stat().st_mtime_ns)).encode()).hexdigest()
        cache_dir = PROJECT_ROOT / "indexes" / "amazon"
        cache_dir.mkdir(parents=True, exist_ok=True)
        vectors_path = cache_dir / (cache_key + ".npz")
        if vectors_path.exists():
            print("Loading saved Amazon vector index...", flush=True)
            with np.load(vectors_path, allow_pickle=False) as cached:
                if cached["ids"].tolist() != [p["id"] for p in products]:
                    raise ValueError("Cached vector IDs do not match MongoDB.")
                vectors = cached["vectors"]
            semantic.products = products
            semantic.dimension = vectors.shape[1]
            semantic.index = faiss.IndexFlatIP(semantic.dimension)
            semantic.index.add(vectors)
        else:
            print(f"Building vectors for {len(products):,} products on CPU. Search will become ready after indexing.", flush=True)
            semantic.fit(products)
            vectors = semantic.index.reconstruct_n(0, len(products))
            np.savez_compressed(vectors_path, ids=np.array([p["id"] for p in products]), vectors=vectors)
        print("Loading reranker...", flush=True)
        reranker = CrossEncoder(str((PROJECT_ROOT / reranker_path).resolve()),
                                local_files_only=True, device="cpu", max_length=256)
        _search_engine = AmazonSearch(products, semantic, reranker)
        _search_signature = signature
        return _search_engine


def dashboard_data():
    products = load_products()
    queries = []
    bm25 = None
    semantic = None
    if not isinstance(products, list):
        raise FileNotFoundError(
            "Amazon catalog could not be loaded from MongoDB."
        )

    categories = sorted({item.get("category") for item in products if item.get("category")})
    rated_products = [item for item in products if isinstance(item.get("rating"), (int, float))]
    average_rating = (
        sum(item["rating"] for item in rated_products) / len(rated_products)
        if rated_products else None
    )
    return {
        "products": products[:100],
        "displayedProductCount": min(100, len(products)),
        "categories": categories,
        "productCount": len(products),
        "averageRating": average_rating,
        "ratedProductCount": len(rated_products),
        "totalStock": sum(item.get("stock", 0) or 0 for item in products),
        "evalQueries": queries if isinstance(queries, list) else [],
        "benchmark": {
            "bm25": bm25,
            "semantic": semantic,
            "queryCount": len(queries) if isinstance(queries, list) else 0,
        },
        "sources": {
            "catalog": f"MongoDB/{COLLECTION}",
            "queries": None,
            "bm25": "reports/baseline_metrics.json" if bm25 else None,
            "semantic": "reports/dense_metrics.json" if semantic else None,
        },
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "SemanticSearchAPI/1.0"

    def end_headers(self):
        origin = getattr(self, "headers", {}).get("Origin")
        if origin in FRONTEND_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def write_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        request = urlparse(self.path)
        if request.path in ("/", "/api/health"):
            self.write_json(200 if _search_ready.is_set() else 503, {
                "ok": _search_ready.is_set(), "service": "semantic-product-search",
                "status": "ready" if _search_ready.is_set() else ("error" if _search_error else "initializing"),
                "message": _search_error or ("Search is ready." if _search_ready.is_set() else "Preparing the Amazon search index. Check terminal progress."),
                "searchEndpoint": "/api/search?q=wireless+headphones",
            })
            return

        if request.path == "/api/dashboard":
            try:
                self.write_json(200, dashboard_data())
            except (FileNotFoundError, ValueError, PyMongoError) as error:
                self.write_json(503, {"error": str(error)})
            return

        if request.path == "/api/search":
            if not _search_ready.is_set():
                self.write_json(503, {"error": _search_error or "Search is initializing. Wait for indexing to finish."})
                return
            params = parse_qs(request.query)
            query = params.get("q", [""])[0].strip()
            if len(query) > 512:
                self.write_json(400, {"error": "Search queries must be 512 characters or fewer."})
                return
            try:
                engine = get_search_engine()
                fuzzy = params.get("fuzzy", ["1"])[0] != "0"
                payload = engine.search(query, fuzzy=fuzzy)
            except (FileNotFoundError, ValueError, RuntimeError, OSError, PyMongoError) as error:
                self.write_json(503, {"error": str(error)})
                return
            self.write_json(200, payload)
            return

        self.write_json(404, {"error": "Route not found."})

    def log_message(self, format_string, *args):
        message = format_string % args
        message = re.sub(r"(/api/search)\?[^\s\"]+", r"\1", message)
        print(f"[{self.log_date_time_string()}] {message}")


def initialize_search():
    global _search_error
    try:
        get_search_engine()
        _search_ready.set()
        print("Amazon search is ready.", flush=True)
    except Exception as error:
        _search_error = f"Search initialization failed: {error}"
        print(_search_error, flush=True)


if __name__ == "__main__":
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), ApiHandler)
    except OSError as error:
        raise SystemExit(f"Cannot listen on port {PORT}: {error}. Stop the other backend instance first.")
    print(f"Semantic Product Search API listening at http://127.0.0.1:{PORT}", flush=True)
    print("Status: /api/health | Search: /api/search?q=... | Dashboard: /api/dashboard", flush=True)
    Thread(target=initialize_search, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Backend stopped.")
    finally:
        server.server_close()

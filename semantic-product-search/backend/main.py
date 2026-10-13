"""Small local API server for Semantic Product Search."""

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import sys
import threading
from urllib.parse import parse_qs, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.baseline.bm25 import fit_bm25, search_bm25
from src.data.load_data import load_cleaned_products

DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
PRODUCTS_PATH = DATA_DIR / "processed" / "products_cleaned.json"
EVAL_PATH = DATA_DIR / "eval" / "eval_set.json"
BM25_REPORT_PATH = REPORTS_DIR / "baseline_metrics.json"
SEMANTIC_REPORT_PATH = REPORTS_DIR / "semantic_metrics.json"
FRONTEND_ORIGINS = {
    origin.strip()
    for origin in os.environ.get(
        "FRONTEND_ORIGINS",
        "http://localhost:3001,http://127.0.0.1:3001",
    ).split(",")
    if origin.strip()
}
PORT = int(os.environ.get("PORT", "8000"))
_catalog_lock = threading.Lock()
_catalog_index = None
_catalog_file_mtime = None


def read_json(path, fallback=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _file_mtime(path):
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def get_catalog_index():
    """Load and index the catalog once, rebuilding if its local JSON changes."""
    global _catalog_index, _catalog_file_mtime
    file_mtime = _file_mtime(PRODUCTS_PATH)
    with _catalog_lock:
        if _catalog_index is not None and file_mtime == _catalog_file_mtime:
            return _catalog_index
        try:
            products = load_cleaned_products(prefer_mongo=not PRODUCTS_PATH.exists())
        except (OSError, json.JSONDecodeError) as error:
            raise FileNotFoundError(
                f"Processed catalog is missing or unreadable. Expected it at {PRODUCTS_PATH}."
            ) from error
        if not isinstance(products, list):
            raise FileNotFoundError(
                f"Processed catalog is missing or unreadable. Expected it at {PRODUCTS_PATH}."
            )
        _catalog_index = fit_bm25(products)
        _catalog_file_mtime = _file_mtime(PRODUCTS_PATH)
        return _catalog_index


def rank_products(index, query, limit=20):
    """Rank products with the shared BM25 implementation and include API scores."""
    matches = search_bm25(index, query, top_k=len(index["products"]))
    return [
        {**product, "score": score} for product, score in matches[:limit]
    ], len(matches)


def dashboard_data():
    index = get_catalog_index()
    products = index["products"]
    queries = read_json(EVAL_PATH, [])
    bm25 = read_json(BM25_REPORT_PATH)
    semantic = read_json(SEMANTIC_REPORT_PATH)
    if not isinstance(products, list):
        raise FileNotFoundError(
            f"Processed catalog not found. Expected it at {PRODUCTS_PATH}."
        )

    categories = sorted({item.get("category") for item in products if item.get("category")})
    rated_products = [item for item in products if isinstance(item.get("rating"), (int, float))]
    average_rating = (
        sum(item["rating"] for item in rated_products) / len(rated_products)
        if rated_products else None
    )
    return {
        "products": products,
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
            "catalog": "data/processed/products_cleaned.json",
            "queries": "data/eval/eval_set.json",
            "bm25": "reports/baseline_metrics.json" if bm25 else None,
            "semantic": "reports/semantic_metrics.json" if semantic else None,
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
        if request.path == "/api/health":
            self.write_json(200, {"ok": True, "service": "semantic-product-search"})
            return

        if request.path == "/api/dashboard":
            try:
                self.write_json(200, dashboard_data())
            except FileNotFoundError as error:
                self.write_json(503, {"error": str(error)})
            return

        if request.path == "/api/search":
            query = parse_qs(request.query).get("q", [""])[0].strip()
            try:
                index = get_catalog_index()
            except FileNotFoundError as error:
                self.write_json(503, {"error": str(error)})
                return
            results, total = rank_products(index, query)
            self.write_json(200, {"query": query, "total": total, "results": results})
            return

        self.write_json(404, {"error": "Route not found."})

    def log_message(self, format_string, *args):
        message = format_string % args
        message = re.sub(r"(/api/search)\?[^\s\"]+", r"\1", message)
        print(f"[{self.log_date_time_string()}] {message}")


if __name__ == "__main__":
    print(f"Semantic Product Search API listening at http://127.0.0.1:{PORT}")
    print("Routes: /api/health, /api/dashboard, /api/search?q=...")
    print(f"Catalog: {PRODUCTS_PATH}")
    try:
        get_catalog_index()
    except FileNotFoundError as error:
        print(error)
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), ApiHandler).serve_forever()
    except KeyboardInterrupt:
        print("\nBackend stopped.")

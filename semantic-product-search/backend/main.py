"""Small local API server for Semantic Product Search."""

from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
PRODUCTS_PATH = DATA_DIR / "processed" / "products_cleaned.json"
EVAL_PATH = DATA_DIR / "eval" / "eval_set.json"
BM25_REPORT_PATH = REPORTS_DIR / "baseline_metrics.json"
SEMANTIC_REPORT_PATH = REPORTS_DIR / "dense_metrics.json"
FRONTEND_ORIGINS = set(os.environ.get(
    "FRONTEND_ORIGINS",
    "http://localhost:3001,http://127.0.0.1:3001",
).split(","))
PORT = int(os.environ.get("PORT", "8000"))
TOKEN_PATTERN = re.compile(r"\b\w+\b")


def read_json(path, fallback=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def tokenize(text):
    return TOKEN_PATTERN.findall((text or "").lower())


def rank_products(products, query, limit=20):
    """Rank catalog products with the project's BM25 scoring formula."""
    query_words = tokenize(query)
    if not query_words:
        return [], 0

    word_counts = []
    document_frequency = Counter()
    for product in products:
        text = product.get("representation_text") or (
            f"{product.get('title', '')} {product.get('description', '')}"
        )
        counts = Counter(tokenize(text))
        word_counts.append(counts)
        document_frequency.update(counts.keys())

    ranked = []
    total_products = len(products)
    k1 = 1.5
    for product, counts in zip(products, word_counts):
        score = 0.0
        for word in query_words:
            frequency = counts.get(word, 0)
            if not frequency:
                continue
            docs_with_word = document_frequency[word]
            inverse_frequency = math.log(
                (total_products - docs_with_word + 0.5) / (docs_with_word + 0.5) + 1
            )
            score += inverse_frequency * frequency * (k1 + 1) / (frequency + k1)
        if score > 0:
            ranked.append({**product, "score": score})

    ranked.sort(key=lambda product: product["score"], reverse=True)
    return ranked[:limit], len(ranked)


def dashboard_data():
    products = read_json(PRODUCTS_PATH)
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
            "semantic": "reports/dense_metrics.json" if semantic else None,
        },
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "SemanticSearchAPI/1.0"

    def end_headers(self):
        origin = self.headers.get("Origin")
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
            products = read_json(PRODUCTS_PATH)
            if not isinstance(products, list):
                self.write_json(503, {"error": f"Processed catalog not found at {PRODUCTS_PATH}."})
                return
            results, total = rank_products(products, query)
            self.write_json(200, {"query": query, "total": total, "results": results})
            return

        self.write_json(404, {"error": "Route not found."})

    def log_message(self, format_string, *args):
        print(f"[{self.log_date_time_string()}] {format_string % args}")


if __name__ == "__main__":
    print(f"Semantic Product Search API listening at http://127.0.0.1:{PORT}")
    print("Routes: /api/health, /api/dashboard, /api/search?q=...")
    print(f"Catalog: {PRODUCTS_PATH}")
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), ApiHandler).serve_forever()
    except KeyboardInterrupt:
        print("\nBackend stopped.")

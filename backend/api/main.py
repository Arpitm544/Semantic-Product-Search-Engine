"""Function-based API routes. Run this file to start the local backend."""

from contextlib import asynccontextmanager
import os
from pathlib import Path
import sys
from threading import Thread
from time import sleep

# Load settings before importing the database and search modules.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env", override=False)

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
import uvicorn

from api.saved_products import router as saved_products_router
from api.search_history import router as history_router, remember_search
from api.auth import require_session
from api.dashboard import dashboard_data
from api import search_service
from api.search_service import get_search_engine, _search_ready
from src.data.catalog import CatalogUpdatingError
from api.shopping_service import ShoppingError, search_shopping, rank_shopping_response

PORT = int(os.environ.get("PORT", "8000"))
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "FRONTEND_ORIGINS", "http://localhost:3001,http://127.0.0.1:3001"
    ).split(",")
    if origin.strip()
]
_search_error = None


def initialize_search(max_attempts=150, retry_delay=2):
    """Retry catalog publication while health requests report startup progress."""
    global _search_error
    _search_ready.clear()
    _search_error = None
    for attempt in range(max_attempts):
        try:
            get_search_engine()
            _search_ready.set()
            print("Search is ready.", flush=True)
            return
        except Exception as error:
            if isinstance(error, CatalogUpdatingError) and attempt + 1 < max_attempts:
                print(f"Waiting for catalog import: {error}", flush=True)
                sleep(retry_delay)
                continue
            _search_error = f"Search initialization failed: {error}"
            print(_search_error, flush=True)
            return


@asynccontextmanager
async def lifespan(app):
    """FastAPI calls this when the server starts."""
    global _search_error
    _search_ready.clear()
    _search_error = None
    Thread(target=initialize_search, daemon=True).start()
    yield


app = FastAPI(title="Semantic Product Search", lifespan=lifespan)
app.include_router(saved_products_router)
app.include_router(history_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["GET", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def prevent_cached_results(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
@app.get("/api/health")
def check_health():
    """Report whether the search models are ready."""
    ready = _search_ready.is_set()
    error = search_service._search_error or _search_error
    if ready:
        status, message = "ready", "Search is ready."
    elif error:
        status, message = "error", error
    else:
        status, message = "initializing", "Preparing the search index. Check terminal progress."
    return JSONResponse(status_code=200 if ready else 503, content={
        "ok": ready,
        "service": "semantic-product-search",
        "status": status,
        "message": message,
        "searchEndpoint": "/api/search?q=wireless+headphones",
    })


@app.get("/api/dashboard", dependencies=[Depends(require_session)])
def get_dashboard():
    """Return catalog counts, categories, and a preview of products."""
    try:
        return dashboard_data()
    except (OSError, ValueError, PyMongoError) as error:
        return JSONResponse(status_code=503, content={"error": str(error)})


@app.get("/api/search")
def search_products(q: str = "", fuzzy: str = "1", source: str = "mongo", session=Depends(require_session)):
    """Choose MongoDB semantic search or Google Shopping via SerpApi."""
    query = q.strip()
    if source not in ("mongo", "serpapi"):
        return JSONResponse(status_code=400, content={"error": "Choose a valid search source: mongo or serpapi."})
    if len(query) > 512:
        return JSONResponse(status_code=400, content={
            "error": "Search queries must be 512 characters or fewer."
        })
    # Shopping search does not depend on MongoDB or local model readiness.
    if source == "serpapi":
        try:
            payload = rank_shopping_response(search_shopping(query))
            return remember_search(session["sub"], query, (source, fuzzy != "0"), payload)
        except ShoppingError as error:
            return JSONResponse(status_code=error.status, content={
                "error": str(error), "code": error.code, "source": "serpapi",
            })

    if (not _search_ready.is_set() and search_service._search_engine is None
            and not (_search_error or search_service._search_error)):
        message = _search_error or "Search is initializing. Wait for indexing to finish."
        return JSONResponse(status_code=503, content={"error": message})

    try:
        engine = get_search_engine()
    except Exception as error:
        # Initialization includes lazy model imports; all failures remain retryable.
        return JSONResponse(status_code=503, content={"error": str(error)})
    try:
        payload = engine.search(query, fuzzy=fuzzy != "0")
        return remember_search(session["sub"], query, (source, fuzzy != "0"), payload)
    except (ValueError, RuntimeError, OSError, PyMongoError) as error:
        return JSONResponse(status_code=503, content={"error": str(error)})


def start_server():
    """Start Uvicorn, the server that runs FastAPI. Ctrl+C stops it."""
    # Disable access logs to keep search text out of terminal logs.
    uvicorn.run(app, host="127.0.0.1", port=PORT, access_log=False)


if __name__ == "__main__":
    start_server()

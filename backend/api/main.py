"""Function-based API routes. Run this file to start the local backend."""

from contextlib import asynccontextmanager
import os
import logging
from pathlib import Path
import sys
from threading import Event, Thread
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
from api.search_history import router as history_router, remember_search, SearchContext
from api.account_features import router as account_router, load_preferences
from api.price_alerts import router as alerts_router, worker_loop
from api.product_prices import apply_preferences
from api.search_limits import check_search_rate
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
    alerts_stop = Event()
    alerts_thread = None
    if os.environ.get('PRICE_ALERTS_ENABLED', '1') == '1':
        alerts_thread = Thread(target=worker_loop, args=(alerts_stop,), daemon=True)
        alerts_thread.start()
    try:
        yield
    finally:
        alerts_stop.set()
        if alerts_thread:
            alerts_thread.join(timeout=5)


app = FastAPI(title="Semantic Product Search", lifespan=lifespan)
app.include_router(saved_products_router)
app.include_router(history_router)
app.include_router(account_router)
app.include_router(alerts_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
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
        status, message = "error", "Search is temporarily unavailable. Check the server logs."
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
        logging.getLogger(__name__).exception("Catalog summary failed")
        return JSONResponse(status_code=503, content={"error": "The search service is temporarily unavailable. Please try again."})


class SearchOptions:
    def __init__(self, fuzzy: str = "1", source: str = "mongo", preferences: bool = False):
        self.fuzzy = fuzzy != "0"
        self.source = source
        self.preferences = preferences


def search_validation(query, source):
    if source not in ("mongo", "serpapi"):
        return JSONResponse(status_code=400, content={"error": "Choose a valid search source: mongo or serpapi."})
    if len(query) > 512:
        return JSONResponse(status_code=400, content={"error": "Search queries must be 512 characters or fewer."})
    return None


@app.get("/api/search")
def search_products(q: str = "", options: SearchOptions = Depends(SearchOptions), session=Depends(require_session)):
    """Choose MongoDB semantic search or Google Shopping via SerpApi."""
    query = q.strip()
    invalid = search_validation(query, options.source)
    if invalid is not None:
        return invalid
    if query:
        check_search_rate(session["sub"], options.source)
    try:
        values = load_preferences(session['sub']) if options.preferences else None
    except PyMongoError:
        return JSONResponse(status_code=503, content={'error': 'Saved preferences are unavailable. Turn off saved preferences or try again.'})
    context = SearchContext(session['sub'], query, options.source, options.fuzzy, options.preferences)
    if options.source == "serpapi":
        return shopping_search(context, values)
    return catalog_search(context, values)


def shopping_search(context, preferences):
    try:
        payload = rank_shopping_response(search_shopping(context.query))
        return finish_search(context, payload, preferences)
    except ShoppingError as error:
        return JSONResponse(status_code=error.status, content={
            "error": str(error), "code": error.code, "source": "serpapi",
        })


def search_initializing():
    if _search_ready.is_set():
        return False
    if search_service._search_engine is not None:
        return False
    return not (_search_error or search_service._search_error)


def search_unavailable():
    return JSONResponse(status_code=503, content={"error": "The search service is temporarily unavailable. Please try again."})


def catalog_search(context, preferences):
    if search_initializing():
        return JSONResponse(status_code=503, content={"error": "Search is initializing. Wait for indexing to finish."})
    try:
        engine = get_search_engine()
    except Exception:
        logging.getLogger(__name__).exception("Search initialization failed")
        return search_unavailable()
    try:
        payload = engine.search(context.query, fuzzy=context.fuzzy)
        return finish_search(context, payload, preferences)
    except (ValueError, RuntimeError, OSError, PyMongoError):
        logging.getLogger(__name__).exception("Search request failed")
        return search_unavailable()


def finish_search(context, payload, preferences):
    if preferences is not None:
        payload = apply_preferences(payload, preferences)
    return remember_search(context, payload)


def start_server():
    """Start Uvicorn, the server that runs FastAPI. Ctrl+C stops it."""
    # Disable access logs to keep search text out of terminal logs.
    uvicorn.run(app, host="127.0.0.1", port=PORT, access_log=False)


if __name__ == "__main__":
    start_server()

"""Function-based API routes. Run this file to start the local backend."""

from contextlib import asynccontextmanager
import os
from pathlib import Path
import sys
from threading import Event, Thread

# Load settings before importing the database and search modules.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env", override=False)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
import uvicorn

from api.dashboard import dashboard_data
from api.search_service import get_search_engine

PORT = int(os.environ.get("PORT", "8000"))
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "FRONTEND_ORIGINS", "http://localhost:3001,http://127.0.0.1:3001"
    ).split(",")
    if origin.strip()
]
_search_ready = Event()
_search_error = None


def initialize_search():
    """Load models in the background so health requests can report progress."""
    global _search_error
    try:
        get_search_engine()
        _search_ready.set()
        print("Search is ready.", flush=True)
    except Exception as error:
        _search_error = f"Search initialization failed: {error}"
        print(_search_error, flush=True)


@asynccontextmanager
async def lifespan(app):
    """FastAPI calls this when the server starts."""
    global _search_error
    _search_ready.clear()
    _search_error = None
    Thread(target=initialize_search, daemon=True).start()
    yield


app = FastAPI(title="Semantic Product Search", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
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
    if ready:
        status, message = "ready", "Search is ready."
    elif _search_error:
        status, message = "error", _search_error
    else:
        status, message = "initializing", "Preparing the search index. Check terminal progress."
    return JSONResponse(status_code=200 if ready else 503, content={
        "ok": ready,
        "service": "semantic-product-search",
        "status": status,
        "message": message,
        "searchEndpoint": "/api/search?q=wireless+headphones",
    })


@app.get("/api/dashboard")
def get_dashboard():
    """Return catalog counts, categories, and a preview of products."""
    try:
        return dashboard_data()
    except (OSError, ValueError, PyMongoError) as error:
        return JSONResponse(status_code=503, content={"error": str(error)})


@app.get("/api/search")
def search_products(q: str = "", fuzzy: str = "1"):
    """Search for q. Set fuzzy=0 to turn off spelling correction."""
    if not _search_ready.is_set():
        message = _search_error or "Search is initializing. Wait for indexing to finish."
        return JSONResponse(status_code=503, content={"error": message})

    query = q.strip()
    if len(query) > 512:
        return JSONResponse(status_code=400, content={
            "error": "Search queries must be 512 characters or fewer."
        })
    try:
        engine = get_search_engine()
        return engine.search(query, fuzzy=fuzzy != "0")
    except (ValueError, RuntimeError, OSError, PyMongoError) as error:
        return JSONResponse(status_code=503, content={"error": str(error)})


def start_server():
    """Start Uvicorn, the server that runs FastAPI. Ctrl+C stops it."""
    # Disable access logs to keep search text out of terminal logs.
    uvicorn.run(app, host="127.0.0.1", port=PORT, access_log=False)


if __name__ == "__main__":
    start_server()

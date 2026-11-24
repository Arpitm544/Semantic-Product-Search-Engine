"""Public search-quality report produced by scripts/evaluate_quality.py."""
import json
import logging
from pathlib import Path
from threading import Lock

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.config import PROJECT_ROOT

router = APIRouter(tags=["Search quality"])
logger = logging.getLogger(__name__)

REPORT_PATH = PROJECT_ROOT / "quality" / "quality_report.json"
_cache = {"key": None, "report": None}
_cache_lock = Lock()


def load_report(path: Path | None = None):
    """Read the report once and again only after the file changes."""
    path = path or REPORT_PATH
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    with _cache_lock:
        if _cache["key"] != key:
            report = json.loads(path.read_text())
            if not isinstance(report, dict) or not isinstance(report.get("stages"), list):
                raise ValueError("The quality report has an unexpected shape.")
            _cache.update(key=key, report=report)
        return _cache["report"]


@router.get("/api/quality")
def get_quality_report():
    """Offline relevance and latency for each search stage. No sign-in needed:
    it holds aggregate scores over a public dataset and no user data."""
    try:
        return load_report()
    except FileNotFoundError:
        return JSONResponse(status_code=404, content={
            "error": "No quality report yet. Run scripts/evaluate_quality.py in backend/.",
        })
    except (OSError, ValueError):
        logger.exception("Quality report could not be read")
        return JSONResponse(status_code=503, content={
            "error": "The quality report is temporarily unavailable. Please try again.",
        })

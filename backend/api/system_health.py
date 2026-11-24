"""Live numbers for the System health page.

Any signed-in user sees timings and counts. The text of zero-result searches
comes from all shoppers, so only accounts listed in OBSERVABILITY_ADMINS
(comma-separated Clerk user IDs) can see it.
"""
from fastapi import APIRouter, Depends

from api.auth import require_session
from api.observability import admin_ids, metrics

router = APIRouter(tags=["System health"])


@router.get("/api/observability")
def system_health(session=Depends(require_session)):
    can_see_text = session["sub"] in admin_ids()
    return {**metrics.snapshot(include_queries=can_see_text),
            "viewer": {"userId": session["sub"], "canSeeSearchText": can_see_text}}

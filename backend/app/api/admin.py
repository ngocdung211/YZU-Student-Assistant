"""Protected administrator router for current and future management actions."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.api import documents, search
from app.auth import require_admin
from app.schemas import AdminSession

# Future document routes belong on this guarded router, not the public chat router.
router = APIRouter(prefix="/admin", tags=["Administrator"],
                   dependencies=[Depends(require_admin)])


@router.get("/session", response_model=AdminSession)
def get_session(response: Response,
                claims: Annotated[dict, Depends(require_admin)]) -> AdminSession:
    """Let the login page verify its backend session and show its expiry."""
    response.headers["Cache-Control"] = "no-store"
    return AdminSession(username=claims["sub"], expires_at=claims["exp"])


router.include_router(documents.router)

router.include_router(search.router)

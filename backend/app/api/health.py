"""Separate process liveness from dependency startup checks."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Health"])


@router.get("/health")
async def get_health() -> dict[str, str]:
    """Return process liveness without contacting external services."""
    return {"status": "ok"}


@router.get("/ready")
async def get_readiness(request: Request) -> JSONResponse:
    """Report cached startup checks without additional billable model calls."""
    services = request.app.state.readiness
    ready = all(value["status"] == "ready" for value in services.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready",
                 "checked_at": "startup", "services": services},
    )

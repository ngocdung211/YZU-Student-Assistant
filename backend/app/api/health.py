"""Liveness endpoint for checking the local API process."""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def get_health() -> dict[str, str]:
    """Return process liveness without contacting external services."""
    # Liveness stays available even before model and storage setup is complete.
    return {"status": "ok"}

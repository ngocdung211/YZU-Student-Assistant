"""Create the FastAPI application and register its HTTP routes."""

from fastapi import FastAPI

from app.api import health

app = FastAPI(
    title="YZU Student Assistant API",
    description="API for the YZU Student Assistant.",
    version="0.1.0",
)
app.include_router(health.router)

"""Create the FastAPI application and register its HTTP routes."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.connections import lifespan

app = FastAPI(
    title="YZU Student Assistant API",
    description="API for the YZU Student Assistant.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET"],
)
app.include_router(health.router)

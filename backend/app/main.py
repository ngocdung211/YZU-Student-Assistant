"""Create the FastAPI application and register its HTTP routes."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, chat, health
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
    allow_methods=["GET", "POST"],
    allow_credentials=True,
    allow_headers=["Content-Type", "X-CSRF-Protection"],
)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(chat.router)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    """Keep rejected password values out of validation error responses."""
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
        for item in error.errors()
    ]})

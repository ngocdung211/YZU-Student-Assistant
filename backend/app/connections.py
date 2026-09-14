"""Initialize and close service clients within the FastAPI lifespan."""

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
import httpx

from app.config import load_settings
from app.models import check_models, create_models
from app.storage.drive import DriveSetupError, check_folder, create_service
from app.storage.neo4j import check_database, create_driver


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Record startup checks and release even partially initialized clients."""
    settings = load_settings()
    app.state.settings = settings
    app.state.connections = {}
    app.state.readiness = {}
    async with AsyncExitStack() as stack:
        for service in ("neo4j", "gemini", "drive"):
            missing = settings.missing(service)
            if missing:
                app.state.readiness[service] = {
                    "status": "not_configured", "missing": missing}
                continue
            try:
                async with asyncio.timeout(45):
                    if service == "neo4j":
                        driver = create_driver(settings)
                        stack.push_async_callback(driver.close)
                        await check_database(driver, settings.require("NEO4J_DATABASE"))
                        app.state.connections[service] = driver
                    elif service == "drive":
                        drive = create_service(settings)
                        stack.callback(drive.close)
                        check_folder(drive, settings.require("GOOGLE_DRIVE_FOLDER_ID"))
                        app.state.connections[service] = drive
                    else:
                        http_client = stack.enter_context(httpx.Client(timeout=20))
                        http_async_client = await stack.enter_async_context(
                            httpx.AsyncClient(timeout=20))
                        chat, embeddings = create_models(
                            settings, http_client, http_async_client)
                        await check_models(chat, embeddings)
                        app.state.connections[service] = (chat, embeddings)
                app.state.readiness[service] = {"status": "ready"}
            except DriveSetupError as error:
                app.state.readiness[service] = {"status": str(error)}
            except Exception:
                # Provider errors can include credentials, URIs, and response bodies.
                app.state.readiness[service] = {"status": "connection_failed"}
        try:
            yield
        finally:
            app.state.connections.clear()

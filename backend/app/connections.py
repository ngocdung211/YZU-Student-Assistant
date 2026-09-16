"""Initialize and close service clients within the FastAPI lifespan."""

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
import httpx

from app.auth import AdminAuth
from app.chat_session import AnonymousChatSessions
from app.config import load_settings
from app.models import check_models, create_models, create_reranker
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService
from app.services.chat import ChatService
from app.services.fallback_tools import FallbackTools
from app.storage.checkpoints import Neo4jSaver
from app.storage.sessions import SessionStore
from app.storage.drive import DriveSetupError, check_folder, create_service
from app.storage.neo4j import check_database, create_driver


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Record startup checks and release even partially initialized clients."""
    settings = load_settings()
    app.state.settings = settings
    app.state.auth = AdminAuth(settings)
    app.state.chat_sessions = AnonymousChatSessions(settings)
    app.state.connections = {}
    app.state.readiness = {}
    fallback_tools = None
    reranker = None
    async with AsyncExitStack() as stack:
        for service in ("neo4j", "gemini", "drive"):
            missing = settings.missing(service)
            if missing:
                app.state.readiness[service] = {
                    "status": "not_configured", "missing": missing}
                print(f"Skipping {service} connection: missing {missing}")
                continue
            try:
                async with asyncio.timeout(45):
                    if service == "neo4j":
                        driver = create_driver(settings)
                        stack.push_async_callback(driver.close)
                        await check_database(driver, settings.require("NEO4J_DATABASE"))
                        app.state.connections[service] = driver
                        print(f"Connected to Neo4j database")
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
                        print(f"Connected to Gemini models: ")
                        reranker = create_reranker(settings, http_client, http_async_client)
                        fallback_tools = FallbackTools(
                            http_async_client,
                            settings.require("GEMINI_API_KEY"),
                            settings.require("GEMINI_CHAT_MODEL_2"),
                        )
                app.state.readiness[service] = {"status": "ready"}
            except DriveSetupError as error:
                app.state.readiness[service] = {"status": str(error)}
            except Exception:
                # Provider errors can include credentials, URIs, and response bodies.
                app.state.readiness[service] = {"status": "connection_failed"}
        app.state.ingestion = None
        if all(name in app.state.connections for name in ("neo4j", "gemini", "drive")):
            app.state.ingestion = IngestionService(
                settings, app.state.connections["neo4j"],
                app.state.connections["gemini"][1], app.state.connections["drive"])
        app.state.retrieval = None
        if "neo4j" in app.state.connections:
            pair = app.state.connections.get("gemini")
            app.state.retrieval = RetrievalService(
                settings, app.state.connections["neo4j"],
                pair[1] if pair else None, reranker)
        app.state.chat = None
        if app.state.retrieval is not None and "gemini" in app.state.connections:
            try:
                saver = Neo4jSaver(app.state.connections["neo4j"],
                                  settings.require("NEO4J_DATABASE"))
                await saver.setup()
                app.state.chat = ChatService(
                    app.state.connections["gemini"][0], app.state.retrieval,
                    SessionStore(saver), saver, fallback_tools=fallback_tools)
                app.state.readiness["chat"] = {"status": "ready"}
            except Exception:
                app.state.readiness["chat"] = {"status": "connection_failed"}
        try:
            yield
        finally:
            app.state.connections.clear()
            app.state.auth.sessions.clear()

"""Coordinate a PDF import without publishing partial searchable content."""

import asyncio
from curses import error
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from fastapi import UploadFile

from app.config import BACKEND_DIRECTORY, Settings
from app.utils.chunking import chunk_pages
from app.utils.pdf import MAX_PDF_BYTES, extract_pdf
from app.storage import documents, drive


class IngestionError(Exception):
    """Safe import failure details, without provider exception bodies."""

    def __init__(self, stage: str, document_id: str, cleanup_required: bool = False):
        super().__init__(f"PDF import failed during {stage}.")
        self.stage = stage
        self.document_id = document_id
        self.cleanup_required = cleanup_required


class IngestionService:
    """Serialize local imports to protect the shared Drive HTTP transport."""

    def __init__(self, settings: Settings, driver, embeddings, drive_service):
        self.settings = settings
        self.driver = driver
        self.embeddings = embeddings
        self.drive = drive_service
        self.lock = asyncio.Lock()

    async def ingest(self, upload: UploadFile) -> dict:
        """Validate and import an upload using an isolated temporary directory."""
        document_id = str(uuid4())
        filename = Path((upload.filename or "").replace("\\", "/")).name
        if not filename.lower().endswith(".pdf") or upload.content_type not in (
                "application/pdf", "application/octet-stream"):
            raise IngestionError("validation", document_id)
        with TemporaryDirectory(prefix="yzu-pdf-") as temporary:
            path = Path(temporary) / "source.pdf"
            size = 0
            checksum = hashlib.sha256()
            with path.open("wb") as output:
                while data := await upload.read(1024 * 1024):
                    size += len(data)
                    if size > MAX_PDF_BYTES:
                        raise IngestionError("size_limit", document_id)
                    checksum.update(data)
                    output.write(data)
            with path.open("rb") as source:
                if source.read(5) != b"%PDF-":
                    raise IngestionError("validation", document_id)
            async with self.lock:
                # Finish any in-flight writes before releasing the lock or deleting temp files.
                task = asyncio.create_task(self._import(path, filename, document_id, checksum.hexdigest()))
                try:
                    return await asyncio.shield(task)
                except asyncio.CancelledError:
                    await task
                    raise

    async def _import(self, path: Path, filename: str, document_id: str, checksum: str) -> dict:
        """Extract and embed before Drive upload; atomically commit ready records."""
        stage = "extraction"
        drive_id = None
        database_write_started = False
        database = self.settings.require("NEO4J_DATABASE")
        try:
            pages = await asyncio.to_thread(extract_pdf, path)
            stage = "chunking"
            chunks = chunk_pages(pages)
            if not chunks:
                raise ValueError("No text chunks were extracted.")
            stage = "embedding"
            texts = [f"{chunk.heading_path}\n{chunk.text}".strip() for chunk in chunks]
            vectors = []
            for offset in range(0, len(texts), 16):
                vectors.extend(await self.embeddings.aembed_documents(texts[offset:offset + 16]))
            dimensions = len(vectors[0]) if vectors else 0
            if (len(vectors) != len(chunks) or not dimensions or any(
                    len(vector) != dimensions or not any(vector)
                    or not all(math.isfinite(value) for value in vector) for vector in vectors)):
                raise ValueError("Embedding output was incomplete or invalid.")
            stage = "index_setup"
            await documents.prepare_indexes(self.driver, database, dimensions)
            stage = "drive_upload"
            drive_id = await asyncio.to_thread(
                drive.upload_pdf, self.drive, path, filename,
                self.settings.require("GOOGLE_DRIVE_FOLDER_ID"), document_id)
            stage = "public_sharing"
            source_url = await asyncio.to_thread(drive.publish_pdf, self.drive, drive_id)
            document = {
                "document_id": document_id, "filename": filename,
                "source_type": "pdf", "source_url": source_url, "drive_file_id": drive_id,
                "sha256": checksum, "page_count": len(pages), "chunk_count": len(chunks),
                "embedding_model": self.settings.require("GEMINI_EMBEDDING_MODEL"),
                "embedding_dimensions": dimensions, "status": "ready",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            records = [asdict(chunk) | {
                "chunk_id": f"{document_id}:{index}", "document_id": document_id,
                "embedding": vector, "source_url": source_url,
            } for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))]
            stage = "database_write"
            database_write_started = True
            await documents.save_document(self.driver, database, document, records)
            return document
        except Exception as error:
            print(f"Ingestion failed at stage={stage}: {type(error).__name__}: {error}")
            cleanup_required = False
            if database_write_started:
                try:
                    await documents.remove_import(self.driver, database, document_id)
                except Exception:
                    cleanup_required = True
            if drive_id and not cleanup_required:
                try:
                    await asyncio.to_thread(drive.delete_import_pdf, self.drive, drive_id)
                except Exception:
                    cleanup_required = True
            if cleanup_required or stage == "drive_upload":
                # A lost upload response may have created a file; appProperties identifies it.
                recovery = BACKEND_DIRECTORY / "data" / "failed-imports"
                recovery.mkdir(parents=True, exist_ok=True)
                (recovery / f"{document_id}.json").write_text(json.dumps({
                    "document_id": document_id, "drive_file_id": drive_id,
                    "stage": stage, "status": "cleanup_required",
                }, indent=2))
                cleanup_required = True
            raise IngestionError(stage, document_id, cleanup_required) from None

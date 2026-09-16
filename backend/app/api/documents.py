"""Authenticated PDF upload and source/chunk inspection endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.services.ingestion import IngestionError, IngestionService
from app.storage.documents import (
    delete_document,
    get_document,
    update_document,
)
router = APIRouter(prefix="/documents")
from pydantic import BaseModel, ConfigDict, Field


class DocumentUpdate(BaseModel):
    """Editable document metadata."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)


def get_ingestion(request: Request) -> IngestionService:
    """Require the three configured import dependencies."""
    service = getattr(request.app.state, "ingestion", None)
    if service is None:
        raise HTTPException(503, "Import connections are unavailable. Check /ready and restart the backend.")
    return service


@router.post("", status_code=201, summary="Upload a PDF and prepare its embeddings")
async def upload_document(
    file: Annotated[UploadFile, File(description="PDF, up to 20 MiB and 100 pages")],
    service: Annotated[IngestionService, Depends(get_ingestion)],
) -> dict:
    """Return ready source metadata only after the whole import succeeds."""
    try:
        return await service.ingest(file)
    except IngestionError as error:
        messages = {
            "validation": "Choose a valid PDF file with a .pdf filename.",
            "size_limit": "PDF exceeds the 20 MiB upload limit.",
            "extraction": "PDF extraction failed. Check that it is readable, unencrypted, at most 100 pages, and that Docling models are available.",
            "chunking": "The PDF produced no readable passages.",
            "embedding": "Embedding failed. Check the configured Gemini model, quota and connection.",
            "index_setup": "Neo4j index setup failed. Check schema permissions and embedding dimensions.",
            "drive_upload": "Drive upload failed. Check folder access and available storage.",
            "public_sharing": "Drive could not create a public reference. Check sharing permissions.",
            "database_write": "Neo4j could not commit the import. Check database connectivity.",
        }
        code = 413 if error.stage == "size_limit" else 422 if error.stage in {
            "validation", "extraction", "chunking"} else 502
        raise HTTPException(code, {"stage": error.stage, "message": messages[error.stage],
                                   "document_id": error.document_id,
                                   "cleanup_required": error.cleanup_required}) from None
    finally:
        await file.close()


@router.get("/{document_id}", summary="Inspect imported source metadata and chunks")
async def inspect_document(document_id: str,
                           service: Annotated[IngestionService, Depends(get_ingestion)]) -> dict:
    """Read persisted passages with page citations, without exposing vectors."""
    try:
        document = await get_document(service.driver,
                                      service.settings.require("NEO4J_DATABASE"), document_id)
    except Exception:
        raise HTTPException(503, "Document storage is unavailable.") from None
    if document is None:
        raise HTTPException(404, "Document not found.")
    return document

@router.delete(
    "/{document_id}",
    status_code=204,
    summary="Delete an imported document and its chunks",
)
async def remove_document(
    document_id: str,
    service: Annotated[IngestionService, Depends(get_ingestion)],
) -> None:
    """Delete document metadata and all associated chunks."""
    document = await get_document(
        service.driver,
        service.settings.require("NEO4J_DATABASE"),
        document_id,
    )

    if document is None:
        return False

    drive_file_id = document["document"].get("drive_file_id")

    if drive_file_id:
        service.drive.files().delete(
            fileId=drive_file_id
        ).execute()
    try:
        deleted = await delete_document(
            service.driver,
            service.settings.require("NEO4J_DATABASE"),
            document_id,
        )
    except Exception:
        raise HTTPException(
            503,
            "Document storage is unavailable.",
        ) from None

    if not deleted:
        raise HTTPException(
            404,
            "Document not found.",
        )


@router.patch(
    "/{document_id}",
    summary="Edit imported document metadata",
)
async def edit_document(
    document_id: str,
    body: DocumentUpdate,
    service: Annotated[IngestionService, Depends(get_ingestion)],
) -> dict:
    """Update editable metadata without regenerating chunks."""

    updates = body.model_dump(exclude_none=True)

    if not updates:
        raise HTTPException(
            422,
            "Provide at least one field to update.",
        )

    try:
        document = await update_document(
            service.driver,
            service.settings.require("NEO4J_DATABASE"),
            document_id,
            updates,
        )
    except Exception:
        raise HTTPException(
            503,
            "Document storage is unavailable.",
        ) from None

    if document is None:
        raise HTTPException(
            404,
            "Document not found.",
        )

    return document
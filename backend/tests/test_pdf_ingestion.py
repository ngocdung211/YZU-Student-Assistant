"""Verify source fidelity, authorization, isolation, and import compensation."""

import asyncio
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from starlette.datastructures import Headers, UploadFile
import pytest

from app import connections
from pwdlib import PasswordHash
from app.api import documents as document_api
from app.config import Settings
from app.utils import pdf
from app.utils.chunking import chunk_pages
from app.main import app
from app.services import ingestion
from app.services.ingestion import IngestionError, IngestionService
from app.storage import drive


def upload(content=b"%PDF-1.7 test", filename="source.pdf", mime="application/pdf"):
    return UploadFile(io.BytesIO(content), filename=filename,
                      headers=Headers({"content-type": mime}))


@pytest.fixture
def service(monkeypatch, tmp_path):
    monkeypatch.setattr(ingestion, "BACKEND_DIRECTORY", tmp_path)
    monkeypatch.setattr(ingestion, "extract_pdf", lambda path: [(1, "# Eligibility\nRequired grades."), (2, "# Duration\nFour semesters.")])
    monkeypatch.setattr(ingestion.documents, "prepare_indexes", AsyncMock())
    monkeypatch.setattr(ingestion.documents, "save_document", AsyncMock())
    monkeypatch.setattr(ingestion.documents, "remove_import", AsyncMock())
    monkeypatch.setattr(ingestion.drive, "upload_pdf", MagicMock(return_value="new-drive-id"))
    monkeypatch.setattr(ingestion.drive, "publish_pdf", MagicMock(return_value="https://drive.google.com/file/d/new-drive-id/view"))
    monkeypatch.setattr(ingestion.drive, "delete_import_pdf", MagicMock())
    settings = Settings({"NEO4J_DATABASE": "neo4j", "GOOGLE_DRIVE_FOLDER_ID": "test-folder",
                         "GEMINI_EMBEDDING_MODEL": "test-embedding"})
    embeddings = SimpleNamespace(aembed_documents=AsyncMock(side_effect=lambda texts: [[0.1, 0.2] for _ in texts]))
    return IngestionService(settings, object(), embeddings, object())


def test_chunking_preserves_headings_and_actual_pages():
    chunks = chunk_pages([(1, "# Scholarships\n## Eligibility\nGrades required."),
                          (2, "Continuation of eligibility.\n## Duration\nFour semesters.")])
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert any(2 in c.page_numbers and c.heading_path == "Scholarships > Eligibility"
               and "Continuation" in c.text for c in chunks)
    assert all(not ("Grades" in c.text and "Four semesters" in c.text) for c in chunks)
    long_chunks = chunk_pages([(3, "# Long\n" + "a" * 6000)], chunk_size=1000, chunk_overlap=100)
    assert all(len(c.text) <= 1000 and c.page_number == 3 for c in long_chunks)
    assert len(long_chunks) > 6


def test_docling_page_export_and_incomplete_conversion(monkeypatch, tmp_path):
    document = SimpleNamespace(pages={2: object(), 1: object()},
                               export_to_markdown=lambda page_no: f"page {page_no}")
    result = SimpleNamespace(status=pdf.ConversionStatus.SUCCESS, document=document)
    monkeypatch.setattr(pdf, "DocumentConverter", lambda **kwargs: SimpleNamespace(convert=lambda *args, **kwargs: result))
    assert pdf.extract_pdf(tmp_path / "test.pdf") == [(1, "page 1"), (2, "page 2")]
    result.status = pdf.ConversionStatus.PARTIAL_SUCCESS
    with pytest.raises(ValueError, match="incomplete"):
        pdf.extract_pdf(tmp_path / "test.pdf")


@pytest.mark.parametrize("file", [lambda: upload(b"not pdf"), lambda: upload(b""),
                                 lambda: upload(filename="file.txt"), lambda: upload(mime="text/plain")])
def test_invalid_inputs_do_not_reach_providers(service, file):
    with pytest.raises(IngestionError) as error:
        asyncio.run(service.ingest(file()))
    assert error.value.stage == "validation"
    service.embeddings.aembed_documents.assert_not_called()
    ingestion.drive.upload_pdf.assert_not_called()


def test_size_limit(service, monkeypatch):
    monkeypatch.setattr(ingestion, "MAX_PDF_BYTES", 8)
    with pytest.raises(IngestionError) as error:
        asyncio.run(service.ingest(upload()))
    assert error.value.stage == "size_limit"


def test_success_persists_source_and_vectors(service):
    result = asyncio.run(service.ingest(upload(filename="../../source.pdf")))
    assert result["filename"] == "source.pdf"
    assert result["status"] == "ready" and result["chunk_count"] == 2
    assert result["page_count"] == 2 and result["embedding_dimensions"] == 2
    records = ingestion.documents.save_document.call_args.args[3]
    assert all(record["source_url"] == result["source_url"] for record in records)
    assert all(record["document_id"] == result["document_id"] for record in records)
    assert [record["page_number"] for record in records] == [1, 2]
    ingestion.drive.delete_import_pdf.assert_not_called()


def test_concurrent_same_name_uploads_have_isolated_paths(service, monkeypatch):
    paths = []

    def extract(path):
        paths.append(path)
        return [(1, path.read_bytes().decode())]

    monkeypatch.setattr(ingestion, "extract_pdf", extract)

    async def run():
        return await asyncio.gather(service.ingest(upload(b"%PDF-first")),
                                    service.ingest(upload(b"%PDF-second")))

    results = asyncio.run(run())
    assert len(set(paths)) == 2 and all(not path.parent.exists() for path in paths)
    assert results[0]["document_id"] != results[1]["document_id"]
    assert results[0]["sha256"] != results[1]["sha256"]


@pytest.mark.parametrize("target, stage", [("embedding", "embedding"), ("index", "index_setup"),
                                         ("sharing", "public_sharing"), ("database", "database_write")])
def test_failure_compensates_only_created_resources(service, target, stage):
    error = RuntimeError("provider-secret-must-not-leak")
    if target == "embedding":
        service.embeddings.aembed_documents.side_effect = error
    elif target == "index":
        ingestion.documents.prepare_indexes.side_effect = error
    elif target == "sharing":
        ingestion.drive.publish_pdf.side_effect = error
    else:
        ingestion.documents.save_document.side_effect = error
    with pytest.raises(IngestionError) as failure:
        asyncio.run(service.ingest(upload()))
    assert failure.value.stage == stage and "provider-secret" not in str(failure.value)
    assert failure.value.cleanup_required is False
    if target in {"sharing", "database"}:
        ingestion.drive.delete_import_pdf.assert_called_once_with(service.drive, "new-drive-id")
    else:
        ingestion.drive.upload_pdf.assert_not_called()
    if target == "database":
        ingestion.documents.remove_import.assert_awaited_once()


def test_failed_compensation_records_recovery_and_keeps_reference(service, tmp_path):
    ingestion.documents.save_document.side_effect = RuntimeError("commit uncertain")
    ingestion.documents.remove_import.side_effect = RuntimeError("offline")
    with pytest.raises(IngestionError) as failure:
        asyncio.run(service.ingest(upload()))
    assert failure.value.cleanup_required
    assert (tmp_path / "data/failed-imports" / f"{failure.value.document_id}.json").exists()
    ingestion.drive.delete_import_pdf.assert_not_called()


def test_publication_failure_is_not_silently_ignored():
    client = MagicMock()
    client.permissions().create().execute.side_effect = RuntimeError("denied")
    with pytest.raises(RuntimeError):
        drive.publish_pdf(client, "test-id")
    client.files().get.assert_not_called()


def test_pdf_routes_require_admin_and_csrf(monkeypatch, service):
    monkeypatch.setattr(connections, "load_settings", lambda: Settings({}))
    with TestClient(app) as client:
        app.state.ingestion = service
        response = client.post("/admin/documents", files={"file": ("test.pdf", b"%PDF-test", "application/pdf")},
                               headers={"X-CSRF-Protection": "1"})
        assert response.status_code == 401
        assert client.get("/admin/documents/test-id").status_code == 401
        assert client.post("/admin/documents", files={"file": ("test.pdf", b"%PDF-test", "application/pdf")}).status_code == 403
        service.embeddings.aembed_documents.assert_not_called()


@pytest.mark.parametrize("vectors", [[], [[0.0, 0.0], [0.0, 0.0]],
                                     [[float("nan"), 1], [1, 2]], [[1, 2], [1]]])
def test_invalid_embeddings_never_publish(service, vectors):
    service.embeddings.aembed_documents.side_effect = None
    service.embeddings.aembed_documents.return_value = vectors
    with pytest.raises(IngestionError) as error:
        asyncio.run(service.ingest(upload()))
    assert error.value.stage == "embedding"
    ingestion.drive.upload_pdf.assert_not_called()
    ingestion.documents.save_document.assert_not_awaited()


def test_authenticated_upload_and_inspection(monkeypatch, service):
    settings = Settings({"ADMIN_USERNAME": "test-admin",
                         "ADMIN_PASSWORD_HASH": PasswordHash.recommended().hash("test-password"),
                         "AUTH_SECRET": "synthetic-step-four-signing-secret-only"})
    monkeypatch.setattr(connections, "load_settings", lambda: settings)
    stored = {"document": {"document_id": "test-id"}, "chunks": []}
    reader = AsyncMock(return_value=stored)
    monkeypatch.setattr(document_api, "get_document", reader)
    with TestClient(app, base_url="http://localhost:8000") as client:
        app.state.ingestion = service
        headers = {"X-CSRF-Protection": "1"}
        assert client.post("/auth/token", json={"username": "test-admin", "password": "test-password"},
                           headers=headers).status_code == 200
        response = client.post("/admin/documents", headers=headers,
                               files={"file": ("test.pdf", b"%PDF-test", "application/pdf")})
        assert response.status_code == 201
        assert response.json()["status"] == "ready"
        assert client.get("/admin/documents/test-id").json() == stored
        reader.return_value = None
        assert client.get("/admin/documents/missing").status_code == 404
        response = client.post("/admin/documents", headers=headers,
                               files={"file": ("bad.pdf", b"invalid", "application/pdf")})
        assert response.status_code == 422
        assert response.json()["detail"]["stage"] == "validation"



def test_sentence_spanning_pdf_pages_stays_together():
    chunks = chunk_pages([
        (2, "## Stipend review\nThe basic threshold is 4 points for paper publication. The review"),
        (3, "standard may be increased by colleges based on the nature of the field.\n\n## Duration\nEight semesters."),
    ])
    sentence = "The review standard may be increased by colleges based on the nature of the field."
    matches = [chunk for chunk in chunks if sentence in chunk.text]
    assert len(matches) == 1
    assert matches[0].page_numbers == [2, 3]
    assert matches[0].page_number == 2
    assert "Eight semesters" not in matches[0].text
    assert chunks[-1].page_numbers == [3]


def test_page_mapping_survives_overlap_and_repeated_text():
    chunks = chunk_pages([(1, "Alpha sentence. " * 30),
                          (2, "Beta sentence. " * 30),
                          (3, "Alpha sentence. " * 30)],
                         chunk_size=200, chunk_overlap=40)
    assert all(len(chunk.text) <= 200 for chunk in chunks)
    assert chunks[0].page_numbers == [1]
    assert chunks[-1].page_numbers == [3]
    assert all(chunk.page_number == chunk.page_numbers[0] for chunk in chunks)
    assert all(2 in chunk.page_numbers for chunk in chunks if "Beta" in chunk.text)


def test_page_break_does_not_merge_headings_or_list_items():
    chunks = chunk_pages([(1, "## First\nAn incomplete statement"),
                          (2, "## Second\nDifferent policy.\n- Item one"),
                          (3, "- Item two")])
    assert chunks[0].page_numbers == [1]
    assert "Different policy" not in chunks[0].text
    assert "- Item one\n\n- Item two" in chunks[-1].text
    assert chunks[-1].page_numbers == [2, 3]

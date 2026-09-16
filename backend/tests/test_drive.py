"""Verify OAuth setup handling and isolated public-link probe cleanup."""

import asyncio
import json
from unittest.mock import MagicMock

import httpx
import pytest

from app.config import Settings
from app.models import create_models
from app.storage import drive


def test_gemini_request_uses_configured_endpoint_and_raw_embedding_text():
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path.endswith("embeddings"):
            return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2], "index": 0}]})
        return httpx.Response(200, json={"id": "test", "choices": [{"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}]})

    async def run():
        transport = httpx.MockTransport(respond)
        settings = Settings({"GEMINI_API_KEY": "test-key", "GEMINI_BASE_URL": "https://gemini.example.invalid/v1beta/openai/", "GEMINI_CHAT_MODEL_1": "test-chat", "GEMINI_EMBEDDING_MODEL": "test-embedding"})
        with httpx.Client(transport=transport) as sync_client:
            async with httpx.AsyncClient(transport=transport) as async_client:
                chat, embeddings = create_models(settings, sync_client, async_client)
                chat.streaming = False
                await chat.ainvoke("check")
                assert await embeddings.aembed_query("plain text") == [0.1, 0.2]

    asyncio.run(run())
    assert [request.url.path for request in requests] == ["/v1beta/openai/chat/completions", "/v1beta/openai/embeddings"]
    assert all(request.url.host == "gemini.example.invalid" for request in requests)
    assert json.loads(requests[1].content)["input"] == ["plain text"]


def test_missing_token_requires_explicit_authorization(tmp_path):
    with pytest.raises(drive.DriveSetupError, match="oauth_authorization_required"):
        drive.create_service(Settings({"GOOGLE_DRIVE_TOKEN_FILE": str(tmp_path / "token.json")}))


def test_saved_token_is_private(tmp_path):
    path = tmp_path / "token.json"
    path.write_text("old")
    path.chmod(0o644)
    drive.save_token(path, MagicMock(to_json=lambda: "synthetic-token"))
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("metadata, expected", [
    ({"mimeType": "text/plain"}, "invalid_drive_folder"),
    ({"mimeType": "application/vnd.google-apps.folder", "capabilities": {}}, "drive_folder_not_writable"),
])
def test_folder_must_allow_uploads(metadata, expected):
    service = MagicMock()
    service.files().get().execute.return_value = metadata
    with pytest.raises(drive.DriveSetupError, match=expected):
        drive.check_folder(service, "existing-folder")


@pytest.mark.parametrize("share_fails", [False, True])
def test_public_probe_deletes_only_its_own_file(monkeypatch, share_fails):
    service = MagicMock()
    service.files().create().execute.return_value = {"id": "probe-only", "webViewLink": "https://drive.google.com/file/d/probe-only/view"}
    if share_fails:
        service.permissions().create().execute.side_effect = RuntimeError("permission denied")
    anonymous_get = MagicMock(return_value=httpx.Response(200, content=b"YZU Student Assistant public reference connection check."))
    monkeypatch.setattr(httpx, "get", anonymous_get)
    if share_fails:
        with pytest.raises(RuntimeError):
            drive.check_public_reference(service, "existing-folder")
        anonymous_get.assert_not_called()
    else:
        drive.check_public_reference(service, "existing-folder")
        assert "headers" not in anonymous_get.call_args.kwargs
        assert "auth" not in anonymous_get.call_args.kwargs
    service.files().delete.assert_called_once_with(fileId="probe-only", supportsAllDrives=True)

"""Verify signed anonymous sessions and the public SSE chat contract."""

import json
from unittest.mock import AsyncMock
from uuid import UUID

from fastapi.testclient import TestClient
import pytest

from app import connections
from app.chat_session import AnonymousChatSessions, CHAT_COOKIE_NAME
from app.config import Settings
from app.main import app


AUTH_SECRET = "step-nine-test-signing-secret-with-at-least-32-characters"
HEADERS = {"X-CSRF-Protection": "1"}


class FakeChatService:
    """Record API-owned session IDs without contacting models or Neo4j."""

    def __init__(self):
        self.ask = AsyncMock(return_value={
            "session_id": "must-not-be-public",
            "turn_id": "turn-1",
            "status": "answered",
            "answer": "| Requirement | Value |\n|---|---|\n| GPA | 3.5 |",
            "references": [{
                "source_id": "chunk-1",
                "chunk_id": "chunk-1",
                "document_id": "document-1",
                "title": "Scholarship rules",
                "source_url": "https://drive.google.com/file/d/test/view",
                "page_numbers": [2, 3],
                "source_type": "document",
            }],
            "tools_used": [],
            "action_required": False,
            "action_status": "not_requested",
        })
        self.transcript = AsyncMock(return_value=[])
        self.reset = AsyncMock()


@pytest.fixture
def client(monkeypatch):
    settings = Settings({"AUTH_SECRET": AUTH_SECRET})
    monkeypatch.setattr(connections, "load_settings", lambda: settings)
    with TestClient(app, base_url="http://localhost:8000") as test_client:
        service = FakeChatService()
        app.state.chat = service
        yield test_client, service


def parse_events(response) -> list[tuple[str, dict]]:
    """Parse complete server events; browser split buffering is tested separately."""
    events = []
    event_name = None
    for line in response.text.splitlines():
        if line.startswith("event: "):
            event_name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            events.append((event_name, json.loads(line.removeprefix("data: "))))
    return events


def test_session_tokens_accept_only_signed_uuid_claims():
    sessions = AnonymousChatSessions(Settings({"AUTH_SECRET": AUTH_SECRET}))
    session_id, is_new = sessions.resolve(None)
    assert is_new
    assert str(UUID(session_id)) == session_id

    token = sessions.issue(session_id)
    assert sessions.resolve(token) == (session_id, False)
    replacement, is_new = sessions.resolve(token + "forged")
    assert is_new and replacement != session_id


def test_public_chat_reuses_cookie_and_emits_ordered_events(client):
    browser, service = client
    first = browser.post("/chat", json={"question": "What are the requirements?"},
                         headers=HEADERS)
    assert first.status_code == 200
    assert first.headers["content-type"].startswith("text/event-stream")
    assert CHAT_COOKIE_NAME in first.cookies
    first_session = service.ask.await_args.args[0]
    assert str(UUID(first_session)) == first_session

    events = parse_events(first)
    assert [name for name, _ in events] == [
        "start", "answer", "references", "complete"]
    assert events[1][1]["answer"].startswith("| Requirement")
    assert "session_id" not in events[1][1]
    assert events[2][1]["references"][0]["page_numbers"] == [2, 3]

    browser.post("/chat", json={"question": "How long does it last?"},
                 headers=HEADERS)
    assert service.ask.await_args.args[0] == first_session


def test_forged_cookie_cannot_select_a_session(client):
    browser, service = client
    attacker_choice = "f39ac356-8fe0-4f84-9fc9-147ba0fe863e"
    browser.cookies.set(CHAT_COOKIE_NAME, attacker_choice)
    response = browser.post("/chat", json={"question": "Question"}, headers=HEADERS)
    assert response.status_code == 200
    assert service.ask.await_args.args[0] != attacker_choice


def test_history_is_cookie_bound_and_renews_cookie(client):
    browser, service = client
    service.transcript.return_value = [{
        "turn_id": "turn-1",
        "question": "Question",
        "status": "answered",
        "answer": "Answer",
        "references": [],
        "action_required": False,
        "action_status": "not_requested",
    }]
    response = browser.get("/chat/history")
    assert response.status_code == 200
    assert response.json()["turns"][0]["answer"] == "Answer"
    assert CHAT_COOKIE_NAME in response.cookies
    session_id = service.transcript.await_args.args[0]
    assert str(UUID(session_id)) == session_id


def test_new_conversation_deletes_bound_session_and_rotates_cookie(client):
    browser, service = client
    browser.get("/chat/history")
    old_cookie = browser.cookies.get(CHAT_COOKIE_NAME)
    old_session = service.transcript.await_args.args[0]

    response = browser.post("/chat/new", headers=HEADERS)
    assert response.status_code == 200
    service.reset.assert_awaited_once_with(old_session)
    assert response.json() == {"status": "new_conversation"}
    assert browser.cookies.get(CHAT_COOKIE_NAME) != old_cookie


def test_chat_failure_is_redacted_and_never_completes(client):
    browser, service = client
    service.ask.side_effect = RuntimeError("secret provider response")
    response = browser.post("/chat", json={"question": "Question"}, headers=HEADERS)
    assert response.status_code == 200
    assert parse_events(response) == [("start", {"status": "started"}), (
        "error", {
            "message": "The assistant could not finish this response. Please try again.",
            "retryable": True,
        })]
    assert "secret provider response" not in response.text


def test_chat_rejects_blank_questions_and_missing_csrf(client):
    browser, service = client
    assert browser.post("/chat", json={"question": "   "}, headers=HEADERS).status_code == 422
    assert browser.post("/chat", json={"question": "Question"}).status_code == 403
    service.ask.assert_not_awaited()

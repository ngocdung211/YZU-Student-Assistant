"""Verify administrator authentication without real secrets or provider calls."""

from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient
import jwt
from pwdlib import PasswordHash
import pytest

from app import connections
from app.auth import AdminAuth, COOKIE_NAME, require_admin
from app.config import Settings
from app.main import app

PASSWORD = "synthetic-test-password"
HEADERS = {"X-CSRF-Protection": "1", "Origin": "http://localhost:3000"}


@pytest.fixture(scope="module")
def settings():
    return Settings({"ADMIN_USERNAME": "test-admin",
                     "ADMIN_PASSWORD_HASH": PasswordHash.recommended().hash(PASSWORD),
                     "AUTH_SECRET": "synthetic-signing-key-for-offline-tests-only"})


@pytest.fixture
def client(monkeypatch, settings):
    monkeypatch.setattr(connections, "load_settings", lambda: settings)
    with TestClient(app, base_url="http://localhost:8000") as client:
        yield client


def login(client, **overrides):
    credentials = {"username": "test-admin", "password": PASSWORD} | overrides
    return client.post("/auth/token", json=credentials, headers=HEADERS)


def test_login_cookie_and_backend_access(client):
    assert client.get("/admin/session").status_code == 401
    response = login(client)
    assert response.status_code == 200
    assert response.json()["username"] == "test-admin"
    assert "access_token" not in response.json()
    assert PASSWORD not in response.text
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "max-age=3600" in cookie
    assert client.get("/admin/session").status_code == 200
    assert client.get("/admin/session").headers["cache-control"] == "no-store"


@pytest.mark.parametrize("overrides", [{"username": "unknown"}, {"password": "wrong"}, {"password": ""}])
def test_wrong_credentials_do_not_create_session(client, overrides):
    response = login(client, **overrides)
    assert response.status_code == 401
    assert COOKIE_NAME not in client.cookies
    assert app.state.auth.sessions == {}


def test_logout_revokes_copied_cookie(client):
    assert login(client).status_code == 200
    old_token = client.cookies.get(COOKIE_NAME)
    assert client.post("/auth/logout", headers=HEADERS).status_code == 204
    assert client.get("/admin/session").status_code == 401
    client.cookies.set(COOKIE_NAME, old_token)
    assert client.get("/admin/session").status_code == 401
    assert client.post("/auth/logout", headers=HEADERS).status_code == 204


def test_expired_and_tampered_tokens_denied(client, settings):
    login(client)
    original = client.cookies.get(COOKIE_NAME)
    claims = jwt.decode(original, settings.require("AUTH_SECRET"), algorithms=["HS256"])
    claims["exp"] = claims["iat"] - 1
    expired = jwt.encode(claims, settings.require("AUTH_SECRET"), algorithm="HS256")
    for token in (expired, original + "tampered"):
        client.cookies.clear()
        client.cookies.set(COOKIE_NAME, token)
        assert client.get("/admin/session").status_code == 401


def test_server_expiry_and_restart_invalidate_sessions(client, settings):
    login(client)
    token = client.cookies.get(COOKIE_NAME)
    for session_id in app.state.auth.sessions:
        app.state.auth.sessions[session_id] = 0
    assert client.get("/admin/session").status_code == 401
    with pytest.raises(HTTPException) as error:
        AdminAuth(settings).validate(token)
    assert error.value.status_code == 401


@pytest.mark.parametrize("headers", [{}, {"X-CSRF-Protection": "1", "Origin": "https://untrusted.example"}])
def test_login_and_logout_reject_cross_site_mutations(client, headers):
    response = client.post("/auth/token", json={"username": "test-admin", "password": PASSWORD}, headers=headers)
    assert response.status_code == 403
    assert client.post("/auth/logout", headers=headers).status_code == 403


def test_guard_protects_document_mutations(client):
    # Exercise the dependency future document routes will use, without implementing uploads.
    from fastapi import FastAPI
    protected_app = FastAPI()
    protected_app.state.auth = app.state.auth

    @protected_app.post("/documents", dependencies=[Depends(require_admin)])
    def document_action():
        return {"ok": True}

    with TestClient(protected_app) as documents:
        assert documents.post("/documents", headers=HEADERS).status_code == 401
        login(client)
        documents.cookies.set(COOKIE_NAME, client.cookies.get(COOKIE_NAME))
        assert documents.post("/documents", headers=HEADERS).status_code == 200
        assert documents.post("/documents").status_code == 403


@pytest.mark.parametrize("change", [{"ADMIN_PASSWORD_HASH": ""}, {"AUTH_SECRET": "short"}, {"ADMIN_PASSWORD_HASH": "not-a-hash"}])
def test_incomplete_setup_fails_closed(client, settings, change):
    app.state.auth = AdminAuth(Settings(settings.values | change))
    response = login(client)
    assert response.status_code == 503
    assert "not-a-hash" not in response.text
    assert COOKIE_NAME not in client.cookies
    assert client.get("/health").status_code == 200


def test_cors_allows_credentials_only_from_local_frontend(client):
    response = client.options("/auth/token", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-csrf-protection"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    response = client.options("/auth/token", headers={
        "Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"})
    assert response.status_code == 400


def test_validation_errors_do_not_echo_password_values(client):
    response = client.post("/auth/token", headers=HEADERS,
                           json={"username": "test-admin", "password": {"secret": PASSWORD}})
    assert response.status_code == 422
    assert PASSWORD not in response.text

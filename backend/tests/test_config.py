"""Exercise configuration, safe readiness failures, and connection cleanup."""

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
import pytest

from app import connections
from app.config import Settings, load_settings
from app.main import app


def configured_settings() -> Settings:
    """Return synthetic credentials only; tests never contact providers."""
    return Settings({
        "GEMINI_API_KEY": "test-secret-key",
        "GEMINI_BASE_URL": "https://gemini.example.invalid/v1beta/openai/",
        "GEMINI_CHAT_MODEL_1": "test-chat-model",
        "GEMINI_EMBEDDING_MODEL": "test-embedding-model",
        "NEO4J_URI": "bolt://example.invalid:7687",
        "NEO4J_USERNAME": "test-user",
        "NEO4J_PASSWORD": "test-secret-password",
        "NEO4J_DATABASE": "neo4j",
    })


def test_environment_precedence_and_literal_password(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("NEO4J_PASSWORD='literal-${UNCHANGED}'\nNEO4J_USERNAME=file-user\n")
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    monkeypatch.setenv("NEO4J_USERNAME", "process-user")
    settings = load_settings(env_file)
    assert settings.require("NEO4J_USERNAME") == "process-user"
    assert settings.require("NEO4J_PASSWORD") == "literal-${UNCHANGED}"
    assert "literal" not in repr(settings)


def test_missing_configuration_names_only():
    settings = Settings({"GEMINI_API_KEY": "private-value", "GEMINI_CHAT_MODEL_1": " "})
    assert settings.missing("gemini") == ["GEMINI_BASE_URL", "GEMINI_CHAT_MODEL_1", "GEMINI_EMBEDDING_MODEL"]
    with pytest.raises(ValueError, match="^Missing configuration: GEMINI_CHAT_MODEL_1$"):
        settings.require("GEMINI_CHAT_MODEL_1")


def test_liveness_survives_missing_credentials_without_clients(monkeypatch):
    monkeypatch.setattr(connections, "load_settings", lambda: Settings({}))
    create_driver = MagicMock()
    create_models = MagicMock()
    monkeypatch.setattr(connections, "create_driver", create_driver)
    monkeypatch.setattr(connections, "create_models", create_models)
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json()["services"]["neo4j"]["status"] == "not_configured"
    create_driver.assert_not_called()
    create_models.assert_not_called()


@pytest.mark.parametrize("fail_database", [False, True])
def test_failure_redaction_and_cleanup(monkeypatch, fail_database):
    monkeypatch.setattr(connections, "load_settings", configured_settings)
    driver = MagicMock(close=AsyncMock())
    monkeypatch.setattr(connections, "create_driver", lambda settings: driver)
    check_database = AsyncMock(
        side_effect=RuntimeError("test-secret-password") if fail_database else None)
    monkeypatch.setattr(connections, "check_database", check_database)
    transports = []

    def create_models(settings, sync_client, async_client):
        transports.extend((sync_client, async_client))
        return object(), object()

    monkeypatch.setattr(connections, "create_models", create_models)
    model_check = AsyncMock(side_effect=RuntimeError("test-secret-key"))
    monkeypatch.setattr(connections, "check_models", model_check)
    with TestClient(app) as client:
        response = client.get("/ready")
        assert response.status_code == 503
        assert "test-secret" not in response.text
        assert response.json()["services"]["gemini"]["status"] == "connection_failed"
        assert client.get("/health").status_code == 200
        client.get("/ready")
        assert model_check.await_count == 1
    driver.close.assert_awaited_once()
    assert all(transport.is_closed for transport in transports)
    assert app.state.connections == {}


def test_successful_connections_still_require_drive(monkeypatch):
    monkeypatch.setattr(connections, "load_settings", configured_settings)
    driver = MagicMock(close=AsyncMock())
    monkeypatch.setattr(connections, "create_driver", lambda settings: driver)
    monkeypatch.setattr(connections, "check_database", AsyncMock())
    monkeypatch.setattr(connections, "create_models", lambda *args: (object(), object()))
    monkeypatch.setattr(connections, "check_models", AsyncMock())
    with TestClient(app) as client:
        services = client.get("/ready").json()["services"]
        assert services["neo4j"]["status"] == "ready"
        assert services["gemini"]["status"] == "ready"
        assert services["drive"]["status"] == "not_configured"
        assert client.get("/ready").status_code == 503

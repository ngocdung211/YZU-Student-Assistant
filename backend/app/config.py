"""Load backend configuration without exposing secret values."""

from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import dotenv_values

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
REQUIRED_SETTINGS = {
    "gemini": ("GEMINI_API_KEY", "GEMINI_BASE_URL", "GEMINI_CHAT_MODEL_1",
               "GEMINI_EMBEDDING_MODEL"),
    "drive": ("GOOGLE_DRIVE_FOLDER_ID", "GOOGLE_DRIVE_CREDENTIALS_JSON"),
    "neo4j": ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE"),
}


@dataclass(frozen=True)
class Settings:
    """Keep raw configuration out of generated object representations."""

    values: dict[str, str | None] = field(repr=False)

    def missing(self, service: str) -> list[str]:
        """Return missing variable names, never their values."""
        return [name for name in REQUIRED_SETTINGS[service]
                if not (self.values.get(name) or "").strip()]

    def require(self, name: str) -> str:
        """Read a required value with a safe configuration error."""
        value = self.values.get(name)
        if not value or not value.strip():
            raise ValueError(f"Missing configuration: {name}")
        return value


def load_settings(env_file: Path = BACKEND_DIRECTORY / ".env") -> Settings:
    """Load the backend file; explicit process variables take precedence."""
    # Disable interpolation so literal dollar signs in passwords are preserved.
    values = {"NEO4J_DATABASE": "neo4j"}
    values.update(dotenv_values(env_file, interpolate=False))
    values.update(os.environ)
    return Settings(values)

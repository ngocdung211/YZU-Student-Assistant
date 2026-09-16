"""Administrator password verification and expiring cookie sessions."""

import argparse
from getpass import getpass
import secrets
import time
from typing import Annotated

from dotenv import set_key
from fastapi import Depends, Header, HTTPException, Request
import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.config import BACKEND_DIRECTORY, Settings, load_settings

COOKIE_NAME = "yzu_admin_session"
SESSION_SECONDS = 3600
LOCAL_ORIGINS = {"http://localhost:3000", "http://127.0.0.1:3000",
                 "http://localhost:8000", "http://127.0.0.1:8000"}


class AdminAuth:
    """Manage one configured administrator in a single local API process."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.password_hash = PasswordHash.recommended()
        self.sessions: dict[str, int] = {}

    def check_configuration(self) -> None:
        """Fail closed when the administrator is not configured."""
        names = ("ADMIN_USERNAME", "ADMIN_PASSWORD_HASH", "AUTH_SECRET")
        if any(not self.settings.values.get(name) for name in names):
            raise HTTPException(503, "Administrator setup is incomplete.")
        if len(self.settings.require("AUTH_SECRET")) < 32:
            raise HTTPException(503, "AUTH_SECRET must contain at least 32 characters.")

    def login(self, username: str, password: str) -> tuple[str, int]:
        """Verify the password hash and issue a signed, revocable session."""
        self.check_configuration()
        if not password or len(password) > 1024:
            raise HTTPException(401, "Incorrect username or password.")
        try:
            valid_password = self.password_hash.verify(
                password, self.settings.require("ADMIN_PASSWORD_HASH"))
        except (UnknownHashError, ValueError):
            raise HTTPException(503, "ADMIN_PASSWORD_HASH is invalid.") from None
        if not valid_password or username != self.settings.require("ADMIN_USERNAME"):
            raise HTTPException(401, "Incorrect username or password.")
        now = int(time.time())
        self.sessions = {key: expiry for key, expiry in self.sessions.items() if expiry > now}
        session_id = secrets.token_urlsafe(32)
        expires_at = now + SESSION_SECONDS
        token = jwt.encode({"sub": username, "iat": now, "exp": expires_at,
                            "jti": session_id}, self.settings.require("AUTH_SECRET"),
                           algorithm="HS256")
        self.sessions[session_id] = expires_at
        return token, expires_at

    def validate(self, token: str | None) -> dict:
        """Require a valid signature, expiration, administrator and live session."""
        if not token:
            raise HTTPException(401, "Administrator login required.")
        self.check_configuration()
        try:
            claims = jwt.decode(token, self.settings.require("AUTH_SECRET"),
                                algorithms=["HS256"],
                                options={"require": ["sub", "iat", "exp", "jti"]})
            session_id = claims["jti"]
            if (not isinstance(session_id, str)
                    or claims["sub"] != self.settings.require("ADMIN_USERNAME")
                    or self.sessions.get(session_id, 0) <= time.time()):
                raise jwt.InvalidTokenError()
        except jwt.InvalidTokenError:
            raise HTTPException(401, "Session expired or invalid. Please log in again.") from None
        return claims


def get_auth(request: Request) -> AdminAuth:
    """Return authentication state owned by this application lifespan."""
    return request.app.state.auth


def protect_mutation(
    request: Request,
    x_csrf_protection: Annotated[str | None, Header()] = None,
) -> None:
    """Require an explicit client header and reject foreign browser origins."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    # Foreign browser sites cannot send this header without a CORS preflight.
    origin = request.headers.get("origin")
    if x_csrf_protection != "1" or (origin and origin not in LOCAL_ORIGINS):
        raise HTTPException(403, "Request origin or CSRF protection is invalid.")


def require_admin(
    request: Request,
    auth: Annotated[AdminAuth, Depends(get_auth)],
    protection: Annotated[None, Depends(protect_mutation)],
) -> dict:
    """Backend guard shared by all document-management routes."""
    return auth.validate(request.cookies.get(COOKIE_NAME))


def configure_password() -> None:
    """Prompt locally and save only a hash, without displaying credentials."""
    password = getpass("New administrator password (at least 12 characters): ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation or not 12 <= len(password) <= 1024:
        raise SystemExit("Passwords must match and contain 12–1024 characters.")
    env_file = BACKEND_DIRECTORY / ".env"
    settings = load_settings()
    if not settings.values.get("ADMIN_USERNAME"):
        raise SystemExit("Set ADMIN_USERNAME in backend/.env first.")
    set_key(str(env_file), "ADMIN_PASSWORD_HASH", PasswordHash.recommended().hash(password))
    # A short placeholder signing secret is replaced only by this explicit command.
    if len(settings.values.get("AUTH_SECRET") or "") < 32:
        set_key(str(env_file), "AUTH_SECRET", secrets.token_urlsafe(48))
    env_file.chmod(0o600)
    print("Administrator password configured. Restart the backend to apply it.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set-password", action="store_true", required=True)
    parser.parse_args()
    configure_password()

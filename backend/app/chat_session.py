"""Signed, persistent browser identifiers for anonymous student chats."""

import time
from uuid import UUID, uuid4

from fastapi import HTTPException, Response
import jwt

from app.config import Settings

CHAT_COOKIE_NAME = "yzu_chat_session"
CHAT_SESSION_SECONDS = 365 * 24 * 60 * 60


class AnonymousChatSessions:
    """Issue session IDs that browsers cannot choose or alter."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def check_configuration(self) -> None:
        """Use the existing local signing secret without requiring student login."""
        if len(self.settings.values.get("AUTH_SECRET") or "") < 32:
            raise HTTPException(
                503, "Public chat session setup is incomplete.")

    def issue(self, session_id: str) -> str:
        """Sign one normalized UUID for storage in an HttpOnly cookie."""
        self.check_configuration()
        session_id = str(UUID(session_id))
        now = int(time.time())
        return jwt.encode(
            {
                "typ": "anonymous_chat",
                "sid": session_id,
                "iat": now,
                "exp": now + CHAT_SESSION_SECONDS,
            },
            self.settings.require("AUTH_SECRET"),
            algorithm="HS256",
        )

    def resolve(self, token: str | None) -> tuple[str, bool]:
        """Return a verified UUID or safely replace an invalid browser token."""
        self.check_configuration()
        if token:
            try:
                claims = jwt.decode(
                    token,
                    self.settings.require("AUTH_SECRET"),
                    algorithms=["HS256"],
                    options={"require": ["typ", "sid", "iat", "exp"]},
                )
                if claims["typ"] != "anonymous_chat":
                    raise jwt.InvalidTokenError()
                return str(UUID(claims["sid"])), False
            except (jwt.InvalidTokenError, TypeError, ValueError):
                pass
        return str(uuid4()), True

    def set_cookie(self, response: Response, session_id: str) -> None:
        """Persist and renew the opaque browser session on every chat response."""
        response.set_cookie(
            CHAT_COOKIE_NAME,
            self.issue(session_id),
            max_age=CHAT_SESSION_SECONDS,
            httponly=True,
            samesite="lax",
            secure=False,
            path="/",
        )


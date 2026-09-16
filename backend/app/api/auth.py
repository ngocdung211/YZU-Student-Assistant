"""Administrator login and logout adapted from the HaUI auth routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.auth import AdminAuth, COOKIE_NAME, SESSION_SECONDS, get_auth, protect_mutation
from app.schemas import AdminSession, LoginCredentials

router = APIRouter(prefix="/auth", tags=["Administrator authentication"],
                   dependencies=[Depends(protect_mutation)])


@router.post("/token", response_model=AdminSession)
def login(credentials: LoginCredentials, response: Response,
          auth: Annotated[AdminAuth, Depends(get_auth)]) -> AdminSession:
    """Verify credentials and set the local HttpOnly session cookie."""
    token, expires_at = auth.login(credentials.username, credentials.password.get_secret_value())
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS,
                        httponly=True, samesite="lax", secure=False, path="/")
    response.headers["Cache-Control"] = "no-store"
    return AdminSession(username=credentials.username, expires_at=expires_at)


@router.post("/logout", status_code=204)
def logout(request: Request, auth: Annotated[AdminAuth, Depends(get_auth)]) -> Response:
    """Revoke this session server-side and remove even an expired cookie."""
    try:
        claims = auth.validate(request.cookies.get(COOKIE_NAME))
        auth.sessions.pop(claims["jti"], None)
    except HTTPException as error:
        if error.status_code != 401:
            raise
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax")
    return response

"""Public, cookie-bound student chat endpoints."""

import json
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from app.auth import protect_mutation
from app.chat_session import AnonymousChatSessions, CHAT_COOKIE_NAME
from app.schemas import ChatQuestion
from app.services.chat import ChatService

router = APIRouter(
    prefix="/chat",
    tags=["Student chat"],
    dependencies=[Depends(protect_mutation)],
)


def get_chat(request: Request) -> ChatService:
    """Require the accepted graph and its storage dependencies."""
    service = getattr(request.app.state, "chat", None)
    if service is None:
        raise HTTPException(
            503, "Student chat is unavailable. Check /ready and restart the API.")
    return service


def get_sessions(request: Request) -> AnonymousChatSessions:
    """Return application-owned anonymous-session signing state."""
    return request.app.state.chat_sessions


def event(name: str, data: dict) -> str:
    """Encode one JSON SSE event with a blank-line record delimiter."""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {name}\ndata: {payload}\n\n"


def public_answer(response: dict) -> dict:
    """Remove internal session and source lists split into their own event."""
    return {
        key: response[key]
        for key in (
            "turn_id",
            "status",
            "answer",
            "tools_used",
            "action_required",
            "action_status",
        )
    }


@router.post("", summary="Ask one question and stream workflow-level events")
async def ask_question(
    body: ChatQuestion,
    request: Request,
    service: Annotated[ChatService, Depends(get_chat)],
    sessions: Annotated[AnonymousChatSessions, Depends(get_sessions)],
) -> StreamingResponse:
    """Bind the question to the signed browser session, never a client UUID."""
    session_id, _ = sessions.resolve(request.cookies.get(CHAT_COOKIE_NAME))

    async def stream():
        yield event("start", {"status": "started"})
        try:
            result = await service.ask(session_id, body.question)
        except Exception:
            # Provider failures can contain credentials, URLs, or response bodies.
            yield event("error", {
                "message": (
                    "The assistant could not finish this response. "
                    "Please try again."
                ),
                "retryable": True,
            })
            return
        yield event("answer", public_answer(result))
        yield event("references", {"references": result["references"]})
        yield event("complete", {"status": "complete"})

    response = StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
    sessions.set_cookie(response, session_id)
    return response


@router.get("/history", summary="Restore this browser's completed transcript")
async def get_history(
    request: Request,
    response: Response,
    service: Annotated[ChatService, Depends(get_chat)],
    sessions: Annotated[AnonymousChatSessions, Depends(get_sessions)],
) -> dict:
    """Read only the transcript selected by the verified cookie."""
    session_id, _ = sessions.resolve(request.cookies.get(CHAT_COOKIE_NAME))
    try:
        turns = await service.transcript(session_id)
    except Exception:
        raise HTTPException(503, "Conversation history is unavailable.") from None
    response.headers["Cache-Control"] = "no-store"
    sessions.set_cookie(response, session_id)
    return {"turns": turns}


@router.post("/new", summary="Delete this conversation and start another")
async def new_conversation(
    request: Request,
    service: Annotated[ChatService, Depends(get_chat)],
    sessions: Annotated[AnonymousChatSessions, Depends(get_sessions)],
) -> Response:
    """Delete only the signed session, then rotate to a fresh UUID."""
    session_id, _ = sessions.resolve(request.cookies.get(CHAT_COOKIE_NAME))
    try:
        await service.reset(session_id)
    except Exception:
        raise HTTPException(503, "The conversation could not be reset.") from None
    response = Response(
        content=json.dumps({"status": "new_conversation"}),
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )
    sessions.set_cookie(response, str(uuid4()))
    return response

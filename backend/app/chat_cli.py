"""Local Step 8 driver; no web endpoint or administrator credentials required."""

import argparse
import asyncio
import json
from uuid import uuid4

from app.main import app


async def run(session_id: str):
    """Use the same managed clients as FastAPI and keep session IDs across runs."""
    async with app.router.lifespan_context(app):
        service = getattr(app.state, "chat", None)
        if service is None:
            print("Chat unavailable. Check Neo4j/Gemini configuration and restart.")
            return
        print(f"Session: {session_id}")
        print("Enter a question. /retry resumes failed work; /quit exits.")
        print("/reset deletes this session's history and checkpoints.")
        while True:
            text = await asyncio.to_thread(input, "> ")
            if text == "/quit":
                return
            try:
                if text == "/reset":
                    session_id = await service.reset(session_id)
                    print(f"New session: {session_id}")
                    continue
                result = await service.ask(session_id, None if text == "/retry" else text)
                print(json.dumps(result, indent=2))
            except Exception as error:
                try:
                    stage = await service.pending_stage(session_id)
                except Exception:
                    stage = "checkpoint"
                print(
                    f"Request failed at {stage} ({type(error).__name__}). "
                    "Use /retry for unfinished work."
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default=None)
    arguments = parser.parse_args()
    asyncio.run(run(arguments.session or str(uuid4())))

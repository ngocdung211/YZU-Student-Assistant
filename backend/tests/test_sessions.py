"""Session persistence contracts with a controlled database adapter."""

import asyncio
import json
from unittest.mock import AsyncMock

from app.storage.checkpoints import Neo4jSaver
from app.storage.sessions import SessionStore


def test_history_is_bounded_and_chronological():
    async def scenario():
        saver = Neo4jSaver(None, "test")
        saver.query = AsyncMock(side_effect=[
            [{"session_count": 1}],
            [
                {"question": "new", "answer": "answer"},
                {"question": "old", "answer": "answer"},
                {"question": "too large", "answer": "x" * 12000},
            ],
        ])

        result = await SessionStore(saver).history("session")

        assert [item["question"] for item in result] == ["old", "new"]

    asyncio.run(scenario())


def test_missing_session_skips_turn_relationship_query():
    async def scenario():
        saver = Neo4jSaver(None, "test")
        saver.query = AsyncMock(return_value=[{"session_count": 0}])

        result = await SessionStore(saver).history("new-session")

        assert result == []
        saver.query.assert_awaited_once()
        assert "HAS_TURN" not in saver.query.await_args.args[0]

    asyncio.run(scenario())


def test_transcript_restores_structured_turns_in_display_order():
    async def scenario():
        saver = Neo4jSaver(None, "test")
        stored = {
            "session_id": "private",
            "turn_id": "turn-1",
            "status": "answered",
            "answer": "Answer",
            "references": [{"source_id": "source-1"}],
            "action_required": False,
            "action_status": "not_requested",
        }
        saver.query = AsyncMock(side_effect=[
            [{"session_count": 1}],
            [{"question": "Question", "response": json.dumps(stored)}],
        ])

        turns = await SessionStore(saver).transcript("session")

        assert turns == [{
            "turn_id": "turn-1",
            "question": "Question",
            "status": "answered",
            "answer": "Answer",
            "references": [{"source_id": "source-1"}],
            "action_required": False,
            "action_status": "not_requested",
        }]
        query = saver.query.await_args
        assert "ORDER BY t.sequence ASC" in query.args[0]
        assert query.kwargs["limit"] == 100

    asyncio.run(scenario())


def test_turn_save_is_idempotent_and_reset_is_scoped():
    async def scenario():
        saver = Neo4jSaver(None, "test")
        saver.query = AsyncMock(return_value=[])
        store = SessionStore(saver)

        await store.save(
            "session", "turn", "question", {"answer": "answer"})

        call = saver.query.await_args
        assert "MERGE" in call.args[0] and "ON CREATE" in call.args[0]
        assert "s.last_sequence = s.last_sequence + 1" in call.args[0]
        assert "MERGE (s)-[:HAS_TURN]->(t)" in call.args[0]
        assert call.kwargs["key"] == "session:turn"

        await store.reset("session")

        call = saver.query.await_args
        assert call.kwargs == {
            "thread": "session",
            "threads": ["session", "session"],
        }
        assert "DETACH DELETE n" in call.args[0]

    asyncio.run(scenario())


def test_checkpoint_roundtrip_preserves_pending_writes():
    async def scenario():
        saver = Neo4jSaver(None, "test")
        config = {
            "configurable": {"thread_id": "session", "checkpoint_ns": ""}}
        checkpoint = {
            "id": "checkpoint-2",
            "v": 2,
            "ts": "2026-09-15",
            "channel_values": {"question": "Scholarships?"},
            "channel_versions": {"question": 1},
            "versions_seen": {},
        }
        saver.query = AsyncMock(return_value=[])

        saved_config = await saver.aput(config, checkpoint, {"step": 1}, {})
        node = dict(saver.query.await_args.kwargs["properties"])
        node["key"] = saver.query.await_args.kwargs["key"]
        await saver.aput_writes(
            saved_config, [("question", "updated")], "task")
        write = saver.query.await_args.kwargs["properties"]
        saver.query = AsyncMock(side_effect=[[{"n": node}], [{"w": write}]])

        restored = await saver.aget_tuple(saved_config)

        assert restored.checkpoint == checkpoint
        assert restored.pending_writes == [("task", "question", "updated")]
        assert restored.config == saved_config

    asyncio.run(scenario())

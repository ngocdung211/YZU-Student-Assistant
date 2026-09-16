"""Persistent completed turns, separate from LangGraph execution checkpoints."""

import json


class SessionStore:
    """Keep history in the existing Neo4j database."""

    def __init__(self, saver):
        self.saver = saver

    async def history(self, session_id: str) -> list[dict]:
        sessions = await self.saver.query(
            "MATCH (s:YZUChatSession {key: $thread}) "
            "RETURN count(s) AS session_count",
            thread=session_id,
        )
        if not sessions or sessions[0]["session_count"] == 0:
            return []
        rows = await self.saver.query(
            "MATCH (:YZUChatSession {key: $thread})-[:HAS_TURN]->(t:YZUChatTurn) "
            "RETURN t.question AS question, t.answer AS answer "
            "ORDER BY t.sequence DESC LIMIT 6", thread=session_id)
        retained, characters = [], 0
        for row in rows:
            size = len(row["question"]) + len(row["answer"])
            if characters + size > 12000:
                break
            retained.append(row)
            characters += size
        return list(reversed(retained))

    async def transcript(self, session_id: str, limit: int = 100) -> list[dict]:
        """Return completed turns in display order for browser restoration."""
        sessions = await self.saver.query(
            "MATCH (s:YZUChatSession {key: $thread}) "
            "RETURN count(s) AS session_count",
            thread=session_id,
        )
        if not sessions or sessions[0]["session_count"] == 0:
            return []
        rows = await self.saver.query(
            "MATCH (:YZUChatSession {key: $thread})-[:HAS_TURN]->(t:YZUChatTurn) "
            "RETURN t.question AS question, t.response AS response "
            "ORDER BY t.sequence ASC LIMIT $limit",
            thread=session_id,
            limit=limit,
        )
        turns = []
        for row in rows:
            response = json.loads(row["response"])
            turns.append({
                "turn_id": response["turn_id"],
                "question": row["question"],
                "status": response["status"],
                "answer": response["answer"],
                "references": response.get("references", []),
                "action_required": response.get("action_required", False),
                "action_status": response.get("action_status", "not_requested"),
            })
        return turns

    async def save(self, session_id: str, turn_id: str, question: str, response: dict):
        """Make a replay after a graph failure safe from duplicate turn writes."""
        await self.saver.query(
            "MERGE (s:YZUChatSession {key: $thread}) "
            "ON CREATE SET s.last_sequence = 0, s.created = datetime() "
            "WITH s MERGE (t:YZUChatTurn {key: $key}) "
            "ON CREATE SET t.thread = $thread, t.question = $question, "
            "t.answer = $answer, t.response = $response, "
            "t.sequence = s.last_sequence + 1, t.created = datetime(), "
            "s.last_sequence = s.last_sequence + 1 "
            "MERGE (s)-[:HAS_TURN]->(t)",
            key=f"{session_id}:{turn_id}", thread=session_id, question=question,
            answer=response["answer"], response=json.dumps(response))

    async def reset(self, session_id: str, checkpoint_thread: str | None = None):
        """Delete only this session's turns and checkpoint records atomically."""
        await self.saver.query(
            "MATCH (n) WHERE ((n:YZUChatSession AND n.key = $thread) OR "
            "((n:YZUChatTurn OR n:YZUCheckpoint OR n:YZUCheckpointWrite) "
            "AND n.thread IN $threads)) DETACH DELETE n",
            thread=session_id,
            threads=[session_id, checkpoint_thread or session_id],
        )

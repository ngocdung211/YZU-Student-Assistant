"""Async Neo4j checkpoints for the local, single-graph chat workflow."""

import base64

from langgraph.checkpoint.base import (
    BaseCheckpointSaver, CheckpointTuple, WRITES_IDX_MAP,
    get_checkpoint_metadata,
)


class Neo4jSaver(BaseCheckpointSaver):
    """Persist full snapshots and pending writes using the managed driver."""

    def __init__(self, driver, database: str):
        super().__init__()
        self.driver = driver
        self.database = database

    async def query(self, query: str, **parameters) -> list[dict]:
        """Consume results before closing the async database session."""
        async with self.driver.session(database=self.database) as session:
            result = await session.run(query, **parameters)
            return await result.data()

    async def setup(self) -> None:
        """Create unique keys explicitly, outside module imports."""
        for label in ("YZUCheckpoint", "YZUCheckpointWrite",
                      "YZUChatSession", "YZUChatTurn"):
            await self.query(
                f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.key IS UNIQUE")

    def encode(self, value) -> list[str]:
        """Store typed serializer bytes as a Neo4j-compatible string pair."""
        kind, data = self.serde.dumps_typed(value)
        return [kind, base64.b64encode(data).decode("ascii")]

    def decode(self, value):
        """Restore only data written by the configured checkpoint serializer."""
        return self.serde.loads_typed((value[0], base64.b64decode(value[1])))

    @staticmethod
    def checkpoint_config(thread, namespace, checkpoint_id):
        return {"configurable": {"thread_id": thread, "checkpoint_ns": namespace,
                                 "checkpoint_id": checkpoint_id}}

    async def aget_tuple(self, config):
        options = config["configurable"]
        rows = await self.query(
            "MATCH (n:YZUCheckpoint {thread: $thread, namespace: $namespace}) "
            "WHERE $checkpoint_id IS NULL OR n.checkpoint_id = $checkpoint_id "
            "RETURN n ORDER BY n.checkpoint_id DESC LIMIT 1",
            thread=options["thread_id"], namespace=options.get("checkpoint_ns", ""),
            checkpoint_id=options.get("checkpoint_id"))
        if not rows:
            return None
        node = rows[0]["n"]
        writes = await self.query(
            "MATCH (w:YZUCheckpointWrite {checkpoint_key: $key}) "
            "RETURN w ORDER BY w.task_path, w.task_id, w.idx", key=node["key"])
        return CheckpointTuple(
            config=self.checkpoint_config(node["thread"], node["namespace"], node["checkpoint_id"]),
            checkpoint=self.decode(node["checkpoint"]),
            metadata=self.decode(node["metadata"]),
            parent_config=(self.checkpoint_config(node["thread"], node["namespace"], node["parent"])
                           if node.get("parent") else None),
            pending_writes=[(row["w"]["task_id"], row["w"]["channel"],
                             self.decode(row["w"]["value"])) for row in writes])

    async def alist(self, config, *, filter=None, before=None, limit=None):
        options = (config or {}).get("configurable", {})
        rows = await self.query(
            "MATCH (n:YZUCheckpoint) WHERE ($thread IS NULL OR n.thread = $thread) "
            "AND ($namespace IS NULL OR n.namespace = $namespace) "
            "AND ($before IS NULL OR n.checkpoint_id < $before) "
            "RETURN n ORDER BY n.checkpoint_id DESC",
            thread=options.get("thread_id"), namespace=options.get("checkpoint_ns"),
            before=(before or {}).get("configurable", {}).get("checkpoint_id"))
        count = 0
        for row in rows:
            if limit is not None and count >= limit:
                break
            node = row["n"]
            if (options.get("checkpoint_id")
                    and node["checkpoint_id"] != options["checkpoint_id"]):
                continue
            metadata = self.decode(node["metadata"])
            if any(metadata.get(key) != value for key, value in (filter or {}).items()):
                continue
            yield await self.aget_tuple(self.checkpoint_config(
                node["thread"], node["namespace"], node["checkpoint_id"]))
            count += 1

    async def aput(self, config, checkpoint, metadata, new_versions):
        options = config["configurable"]
        thread, namespace = options["thread_id"], options.get("checkpoint_ns", "")
        key = self.encode([thread, namespace, checkpoint["id"]])[1]
        await self.query(
            "MERGE (n:YZUCheckpoint {key: $key}) SET n += $properties",
            key=key, properties={
                "thread": thread, "namespace": namespace,
                "checkpoint_id": checkpoint["id"], "parent": options.get("checkpoint_id"),
                "checkpoint": self.encode(checkpoint),
                "metadata": self.encode(get_checkpoint_metadata(config, metadata))})
        return self.checkpoint_config(thread, namespace, checkpoint["id"])

    async def aput_writes(self, config, writes, task_id, task_path=""):
        options = config["configurable"]
        checkpoint_key = self.encode([
            options["thread_id"], options.get("checkpoint_ns", ""),
            options["checkpoint_id"]])[1]
        for position, (channel, value) in enumerate(writes):
            index = WRITES_IDX_MAP.get(channel, position)
            key = self.encode([checkpoint_key, task_id, index])[1]
            # Ordinary writes are insert-once; special interrupt/error writes update.
            update = "ON MATCH SET w += $properties " if index < 0 else ""
            await self.query(
                "MERGE (w:YZUCheckpointWrite {key: $key}) "
                "ON CREATE SET w += $properties " + update,
                key=key, properties={
                    "thread": options["thread_id"], "checkpoint_key": checkpoint_key,
                    "task_id": task_id, "task_path": task_path, "idx": index,
                    "channel": channel, "value": self.encode(value)})

    async def adelete_thread(self, thread_id):
        await self.query(
            "MATCH (n) WHERE (n:YZUCheckpoint OR n:YZUCheckpointWrite) "
            "AND n.thread = $thread DELETE n", thread=thread_id)

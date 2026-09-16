"""Persist document/chunk records atomically in the YZU Neo4j namespace."""

from neo4j import AsyncDriver


async def prepare_indexes(driver: AsyncDriver, database: str, dimensions: int) -> None:
    """Create ID constraints and a dimension-compatible vector index."""
    async with driver.session(database=database) as session:
        for query in (
            "CREATE CONSTRAINT yzu_document_id IF NOT EXISTS FOR (d:YZUDocument) REQUIRE d.document_id IS UNIQUE",
            "CREATE CONSTRAINT yzu_chunk_id IF NOT EXISTS FOR (c:YZUChunk) REQUIRE c.chunk_id IS UNIQUE",
        ):
            await (await session.run(query)).consume()
        await (await session.run(
            "CREATE VECTOR INDEX yzu_chunk_embedding IF NOT EXISTS "
            "FOR (c:YZUChunk) ON (c.embedding) OPTIONS {indexConfig: {"
            "`vector.dimensions`: $dimensions, `vector.similarity_function`: 'cosine'}}",
            dimensions=dimensions,
        )).consume()
        result = await session.run(
            "SHOW VECTOR INDEXES YIELD name, options WHERE name = 'yzu_chunk_embedding' RETURN options")
        record = await result.single()
        config = record["options"]["indexConfig"] if record else {}
        if config.get("vector.dimensions") != dimensions:
            raise ValueError("Embedding dimensions do not match the existing YZU index.")
        await (await session.run("CALL db.awaitIndex('yzu_chunk_embedding', 60)")).consume()


async def save_document(driver: AsyncDriver, database: str, document: dict,
                        chunks: list[dict]) -> None:
    """Publish ready metadata and all embedded chunks in one transaction."""
    async def write(tx):
        await (await tx.run(
            "CREATE (d:YZUDocument) SET d = $document "
            "WITH d UNWIND $chunks AS chunk "
            "CREATE (c:YZUChunk) SET c = chunk "
            "CREATE (d)-[:HAS_CHUNK]->(c)",
            document=document, chunks=chunks,
        )).consume()

    async with driver.session(database=database) as session:
        await session.execute_write(write)


async def remove_import(driver: AsyncDriver, database: str, document_id: str) -> None:
    """Compensate only this import, including an uncertain commit result."""
    async with driver.session(database=database) as session:
        await (await session.run(
            "MATCH (d:YZUDocument {document_id: $id}) "
            "OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:YZUChunk) DETACH DELETE c, d",
            id=document_id,
        )).consume()


async def get_document(driver: AsyncDriver, database: str, document_id: str) -> dict | None:
    """Return source metadata and ordered passages without large embedding arrays."""
    async with driver.session(database=database) as session:
        result = await session.run(
            "MATCH (d:YZUDocument {document_id: $id})-[:HAS_CHUNK]->(c:YZUChunk) "
            "WITH d, c ORDER BY c.chunk_index "
            "RETURN properties(d) AS document, collect(c { .chunk_id, .text, "
            ".page_number, .page_numbers, .heading_path, .chunk_index, .source_url, "
            "embedding_dimensions: size(c.embedding)}) AS chunks",
            id=document_id,
        )
        record = await result.single()
        return dict(record) if record else None

async def delete_document(
    driver: AsyncDriver,
    database: str,
    document_id: str,
) -> bool:
    """Delete one document and all chunks owned by it."""

    async with driver.session(database=database) as session:
        result = await session.run(
            """
            MATCH (d:YZUDocument {document_id: $id})
            OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:YZUChunk)
            WITH d, collect(c) AS chunks
            FOREACH (chunk IN chunks | DETACH DELETE chunk)
            DETACH DELETE d
            RETURN true AS deleted
            """,
            id=document_id,
        )

        record = await result.single()
        return record is not None


async def update_document(
    driver: AsyncDriver,
    database: str,
    document_id: str,
    updates: dict,
) -> dict | None:
    """Update document metadata without modifying chunks or embeddings."""

    async with driver.session(database=database) as session:
        result = await session.run(
            """
            MATCH (d:YZUDocument {document_id: $id})
            SET d += $updates
            RETURN properties(d) AS document
            """,
            id=document_id,
            updates=updates,
        )

        record = await result.single()

        return record["document"] if record else None
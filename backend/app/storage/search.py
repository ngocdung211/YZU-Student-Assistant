"""Neo4j search queries with source filtering and original-page provenance."""

from app.schemas import Evidence, SearchFilters

# Static fragments are code-owned; query text, vectors, and filters stay parameters.
SOURCE_FILTER = """
    d.status = 'ready'
    AND ($document_ids = [] OR d.document_id IN $document_ids)
    AND ($source_type IS NULL OR d.source_type = $source_type)
"""
PROJECTION = """c { .chunk_id, .document_id, .text, .chunk_index, .heading_path,
    source_url: d.source_url, title: d.filename,
    page_numbers: coalesce(c.page_numbers, [c.page_number]) } AS passage"""


def parameters(filters: SearchFilters) -> dict:
    """Pass only whitelisted filters to Cypher."""
    return filters.model_dump()


async def prepare_keyword_index(driver, database: str) -> None:
    """Explicitly create and await the English Lucene full-text index."""
    async with driver.session(database=database) as session:
        await (await session.run(
            "CREATE FULLTEXT INDEX yzu_chunk_keywords IF NOT EXISTS "
            "FOR (c:YZUChunk) ON EACH [c.text, c.heading_path] "
            "OPTIONS {indexConfig: {`fulltext.analyzer`: 'english', "
            "`fulltext.eventually_consistent`: false}}"
        )).consume()
        await (await session.run("CALL db.awaitIndex('yzu_chunk_keywords', 60)")).consume()


async def semantic_search(driver, database: str, vector: list[float],
                          embedding_model: str, filters: SearchFilters,
                          limit: int, min_score: float) -> list[Evidence]:
    """Use ANN normally; score the filtered subset exactly for explicit filters."""
    if filters.document_ids or filters.source_type:
        query = "MATCH (d:YZUDocument)-[:HAS_CHUNK]->(c:YZUChunk) WHERE " + SOURCE_FILTER
        query += """ AND d.embedding_model = $model AND size(c.embedding) = size($vector)
            WITH d, c, vector.similarity.cosine(c.embedding, $vector) AS score
            WHERE score >= $min_score """
    else:
        query = """CALL db.index.vector.queryNodes('yzu_chunk_embedding', $pool, $vector)
            YIELD node AS c, score
            MATCH (d:YZUDocument)-[:HAS_CHUNK]->(c) WHERE """ + SOURCE_FILTER
        query += " AND d.embedding_model = $model AND score >= $min_score "
    query += " RETURN " + PROJECTION + ", score ORDER BY score DESC, c.chunk_id LIMIT $limit"
    async with driver.session(database=database) as session:
        result = await session.run(query, **parameters(filters), vector=vector,
                                   model=embedding_model, pool=limit * 5,
                                   limit=limit, min_score=min_score)
        return [Evidence(**record["passage"], scores={"semantic": record["score"]})
                async for record in result]


async def keyword_search(driver, database: str, query_text: str,
                         filters: SearchFilters, limit: int) -> list[Evidence]:
    """Filter Lucene matches before the final result limit."""
    query = """CALL db.index.fulltext.queryNodes('yzu_chunk_keywords', $search_text)
        YIELD node AS c, score
        MATCH (d:YZUDocument)-[:HAS_CHUNK]->(c) WHERE """ + SOURCE_FILTER
    query += " RETURN " + PROJECTION + ", score ORDER BY score DESC, c.chunk_id LIMIT $limit"
    async with driver.session(database=database) as session:
        result = await session.run(
            query, **parameters(filters), search_text=query_text, limit=limit)
        return [Evidence(**record["passage"], scores={"keyword": record["score"]})
                async for record in result]


async def get_neighbors(driver, database: str, selected: list[Evidence]) -> list[Evidence]:
    """Read at most the previous and next chunk of each selected source."""
    async with driver.session(database=database) as session:
        result = await session.run(
            "UNWIND $selected AS anchor "
            "MATCH (d:YZUDocument {document_id: anchor.document_id})-[:HAS_CHUNK]->(c:YZUChunk) "
            "WHERE d.status = 'ready' AND c.chunk_index IN [anchor.chunk_index - 1, anchor.chunk_index + 1] "
            "WITH d, c, collect(DISTINCT anchor.chunk_id) AS neighbor_of "
            "RETURN " + PROJECTION + ", neighbor_of "
            "ORDER BY c.document_id, c.chunk_index",
            selected=[item.model_dump(include={"document_id", "chunk_index", "chunk_id"}) for item in selected],
        )
        return [Evidence(**record["passage"], is_neighbor=True, neighbor_of=record["neighbor_of"])
                async for record in result]

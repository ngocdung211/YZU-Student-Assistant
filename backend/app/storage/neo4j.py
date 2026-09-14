"""Async Neo4j connection adapted from HaUI's database client."""

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.config import Settings


def create_driver(settings: Settings) -> AsyncDriver:
    """Create a driver; connectivity is checked separately during startup."""
    return AsyncGraphDatabase.driver(
        settings.require("NEO4J_URI"),
        auth=(settings.require("NEO4J_USERNAME"),
              settings.require("NEO4J_PASSWORD")),
        connection_timeout=10,
        connection_acquisition_timeout=15,
        max_transaction_retry_time=0,
    )


async def check_database(driver: AsyncDriver, database: str) -> None:
    """Verify authentication and read access to the configured database."""
    await driver.verify_connectivity()
    # A successful handshake alone does not confirm the selected database exists.
    async with driver.session(database=database) as session:
        result = await session.run("RETURN 1 AS connected")
        await result.consume()

"""
database.py
===========
Async MongoDB client using motor.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings

# Create a global client instance
client = AsyncIOMotorClient(settings.MONGO_URL, uuidRepresentation="standard")


def get_db() -> AsyncIOMotorDatabase:
    """
    Dependency that returns the database instance.
    """
    return client[settings.DB_NAME]


async def init_db() -> None:
    """
    Create MongoDB indexes for performance and uniqueness.
    """
    db = get_db()

    # Users indexes
    await db.users.create_index("username", unique=True)
    await db.users.create_index("email", unique=True)

    # Threads indexes
    await db.threads.create_index("user_id")

    # Messages indexes
    await db.messages.create_index("thread_id")
    await db.messages.create_index([("thread_id", 1), ("message_index", 1)])

    # Summaries indexes
    await db.summaries.create_index([("thread_id", 1), ("version", -1)])

    # Documents indexes
    await db.documents.create_index("file_hash", unique=True)

    # Document chunks indexes
    await db.document_chunks.create_index("document_id")
    # Text index for full-text search
    await db.document_chunks.create_index([("content", "text")])

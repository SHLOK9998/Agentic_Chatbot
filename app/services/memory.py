"""
services.memory
================
Conversation memory management with MongoDB.

Implements the "last N messages + rolling summary" pattern:
- **Short-term**: Last ``MEMORY_LAST_N_MESSAGES`` messages for precision.
- **Long-term**: A rolling summary that compresses older messages.
- **Factual grounding**: Retrieved chunks (handled by retrieval service).

The rolling summary is regenerated every ``SUMMARY_UPDATE_INTERVAL``
messages using the LLM itself, then stored as a new versioned document in
the ``summaries`` collection.
"""

import uuid
from datetime import datetime, timezone

from langchain_groq import ChatGroq
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import settings


async def get_recent_messages(
    db: AsyncIOMotorDatabase,
    thread_id: uuid.UUID,
    limit: int | None = None,
) -> list[dict]:
    """
    Fetch the most recent messages from a thread, ordered oldest→newest.

    Args:
        db        : Async MongoDB database.
        thread_id : UUID of the conversation thread.
        limit     : Max messages to return (default: ``MEMORY_LAST_N_MESSAGES``).

    Returns:
        List of message documents.
    """
    limit = limit or settings.MEMORY_LAST_N_MESSAGES
    cursor = db.messages.find({"thread_id": thread_id}).sort("message_index", -1).limit(limit)
    messages = []
    async for msg in cursor:
        msg["id"] = msg["_id"]
        messages.append(msg)
    messages.reverse()  # oldest first
    return messages


async def get_latest_summary(
    db: AsyncIOMotorDatabase,
    thread_id: uuid.UUID,
) -> dict | None:
    """
    Return the most recent rolling summary for a thread, or ``None``
    if no summary exists yet.
    """
    summary = await db.summaries.find_one(
        {"thread_id": thread_id},
        sort=[("version", -1)]
    )
    if summary:
        summary["id"] = summary["_id"]
    return summary


async def get_message_count(db: AsyncIOMotorDatabase, thread_id: uuid.UUID) -> int:
    """Return the total number of messages in a thread."""
    return await db.messages.count_documents({"thread_id": thread_id})


async def should_update_summary(
    db: AsyncIOMotorDatabase,
    thread_id: uuid.UUID,
) -> bool:
    """
    Check whether the rolling summary should be regenerated.

    Returns ``True`` when the number of messages since the last summary
    exceeds ``SUMMARY_UPDATE_INTERVAL``.
    """
    total = await get_message_count(db, thread_id)
    latest = await get_latest_summary(db, thread_id)
    covered = latest["covered_until_index"] if latest else -1
    unsummarised = total - (covered + 1)
    return unsummarised >= settings.SUMMARY_UPDATE_INTERVAL


async def update_rolling_summary(
    db: AsyncIOMotorDatabase,
    thread_id: uuid.UUID,
) -> dict | None:
    """
    Regenerate the rolling summary if needed.

    Uses the LLM to compress all messages up to the current point into
    a concise summary.  The summary is stored as a new versioned document.

    Returns:
        The new summary document, or ``None`` if no update was needed.
    """
    if not await should_update_summary(db, thread_id):
        return None

    cursor = db.messages.find({"thread_id": thread_id}).sort("message_index", 1)
    all_messages = []
    async for msg in cursor:
        msg["id"] = msg["_id"]
        all_messages.append(msg)

    if not all_messages:
        return None

    # Build the conversation text for the summariser.
    conversation_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in all_messages
    )

    # Get the previous summary for continuity.
    prev_summary = await get_latest_summary(db, thread_id)
    prev_text = prev_summary["content"] if prev_summary else "No previous summary."
    prev_version = prev_summary["version"] if prev_summary else 0

    # Use the LLM to generate a new rolling summary.
    llm = ChatGroq(
        model=settings.GROQ_MODEL_NAME,
        groq_api_key=settings.GROQ_API_KEY,
        temperature=0.2,
    )

    prompt = f"""You are a conversation summariser. Your job is to compress the
conversation below into a concise rolling summary that captures:
- Key topics discussed
- Important decisions or facts mentioned
- The user's current intent or task

Previous summary:
{prev_text}

Full conversation:
{conversation_text}

Write a concise summary (max 300 words) that would help an AI assistant
continue this conversation without reading the full history:"""

    response = await llm.ainvoke(prompt)

    # Store the new summary.
    new_summary = {
        "_id": uuid.uuid4(),
        "thread_id": thread_id,
        "content": response.content,
        "version": prev_version + 1,
        "covered_until_index": all_messages[-1]["message_index"],
        "created_at": datetime.now(timezone.utc),
    }
    await db.summaries.insert_one(new_summary)
    new_summary["id"] = new_summary["_id"]

    return new_summary


async def build_memory_context(
    db: AsyncIOMotorDatabase,
    thread_id: uuid.UUID,
) -> dict[str, str]:
    """
    Build the memory context dict to inject into the LLM prompt.

    Returns:
        A dict with keys ``recent_messages`` and ``summary``, both as
        formatted strings ready for prompt injection.
    """
    recent = await get_recent_messages(db, thread_id)
    summary = await get_latest_summary(db, thread_id)

    recent_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in recent
    ) if recent else "No previous messages."

    summary_text = summary["content"] if summary else "No conversation summary available."

    return {
        "recent_messages": recent_text,
        "summary": summary_text,
    }

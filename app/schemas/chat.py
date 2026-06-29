"""
schemas.chat
=============
Pydantic models for the chat API endpoints.

These schemas validate incoming requests and shape outgoing responses.
They are intentionally kept thin — business logic lives in services.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field


# ── Request Schemas ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    """
    Payload sent by the client to ask a question.

    Attributes:
        user_id   : UUID of the authenticated user.
        thread_id : UUID of an existing thread, or ``None`` to start a new one.
        message   : The user's question or instruction.
    """
    user_id: uuid.UUID
    thread_id: uuid.UUID | None = None
    message: str = Field(..., min_length=1, max_length=10000)


class CreateUserRequest(BaseModel):
    """Payload to register a new user."""
    username: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., max_length=255)
    role: str = Field(default="user", pattern=r"^(admin|user)$")


class CreateThreadRequest(BaseModel):
    """Payload to create a new conversation thread."""
    user_id: uuid.UUID
    title: str | None = Field(default=None, max_length=255)


# ── Response Schemas ────────────────────────────────────────────

class SourceChunk(BaseModel):
    """A single source reference returned alongside the answer."""
    document_id: uuid.UUID
    chunk_index: int
    filename: str
    source_page: str | None = None
    relevance_score: float | None = None
    snippet: str

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    """
    Response returned to the client after the agent finishes.

    Attributes:
        thread_id : The thread this answer belongs to.
        answer    : The assistant's generated answer.
        sources   : List of document chunks used as evidence (empty for general chat).
        tool_used : Which LangGraph tool produced the answer (``rag_search`` or ``general_chat``).
    """
    thread_id: uuid.UUID
    answer: str
    sources: list[SourceChunk] = []
    tool_used: str


class ThreadResponse(BaseModel):
    """Summary of a conversation thread."""
    id: uuid.UUID
    user_id: uuid.UUID
    title: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """A single message inside a thread."""
    id: uuid.UUID
    role: str
    content: str
    tool_name: str | None = None
    message_index: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """Public user info."""
    id: uuid.UUID
    username: str
    email: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

"""
schemas.document
=================
Pydantic models for document upload and status endpoints.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    """Returned after a document is accepted for ingestion."""
    document_id: uuid.UUID
    filename: str
    status: str
    message: str


class DocumentStatusResponse(BaseModel):
    """Current processing status of a document."""
    id: uuid.UUID
    filename: str
    file_type: str
    status: str
    total_chunks: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

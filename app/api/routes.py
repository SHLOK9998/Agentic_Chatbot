"""
api.routes
===========
FastAPI route definitions for the RAG chatbot with MongoDB backend.

Endpoints
---------
- ``POST /api/users``                  — Create a new user.
- ``POST /api/threads``                — Create a new conversation thread.
- ``GET  /api/threads/{thread_id}``    — Get thread messages.
- ``POST /api/chat``                   — Send a message and get an AI response.
- ``POST /api/documents/upload``       — Upload a document for ingestion.
- ``GET  /api/documents/{document_id}``— Check document processing status.
- ``GET  /api/health``                 — Health check.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from langchain_core.messages import HumanMessage
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agent.graph import build_graph
from app.agent.state import AgentState
from app.database import get_db
from app.config import settings
from app.schemas.chat import (
    ChatRequest, ChatResponse, SourceChunk,
    CreateUserRequest, UserResponse,
    CreateThreadRequest, ThreadResponse,
    MessageResponse,
)
from app.schemas.document import DocumentUploadResponse, DocumentStatusResponse
from app.schemas.auth import SignupRequest, LoginRequest, AdminUpgradeRequest
from app.services.auth import hash_password, verify_password
from app.services.ingestion import ingest_document
from app.services.memory import (
    build_memory_context,
    get_message_count,
    update_rolling_summary,
)

router = APIRouter(prefix="/api", tags=["chatbot"])


# ────────────────────────────────────────────────────────────────
# Health check
# ────────────────────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "service": "rag-chatbot"}


# ────────────────────────────────────────────────────────────────
# ────────────────────────────────────────────────────────────────
# Authentication
# ────────────────────────────────────────────────────────────────

@router.post("/auth/signup")
async def signup(
    request: SignupRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    if request.password != request.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    # Check if email is already taken
    existing_user = await db.users.find_one({"email": request.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email is already registered")

    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    username = request.name.lower().replace(" ", "_")
    user = {
        "_id": user_id,
        "name": request.name,
        "username": username,
        "email": request.email,
        "password_hash": hash_password(request.password),
        "role": "user",  # default role is user
        "created_at": now,
        "updated_at": now,
    }
    await db.users.insert_one(user)
    return {
        "id": str(user_id),
        "name": request.name,
        "email": request.email,
        "role": "user",
        "created_at": now.isoformat(),
    }


@router.post("/auth/login")
async def login(
    request: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    user = await db.users.find_one({"email": request.email})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    if "password_hash" not in user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    return {
        "id": str(user["_id"]),
        "name": user.get("name", user.get("username")),
        "email": user["email"],
        "role": user.get("role", "user"),
        "created_at": user["created_at"].isoformat() if isinstance(user["created_at"], datetime) else user["created_at"],
    }


@router.post("/auth/verify-admin")
async def verify_admin(
    request: AdminUpgradeRequest,
    user_id: uuid.UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    if request.admin_secret != settings.ADMIN_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin secret key")

    user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.users.update_one(
        {"_id": user_id},
        {"$set": {"role": "admin", "updated_at": datetime.now(timezone.utc)}}
    )

    return {
        "status": "success",
        "message": "User role upgraded to admin successfully.",
        "role": "admin"
    }


# ────────────────────────────────────────────────────────────────
# Users
# ────────────────────────────────────────────────────────────────

@router.post("/users", response_model=UserResponse)
async def create_user(
    request: CreateUserRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Register a new user.

    Args:
        request : ``CreateUserRequest`` with username, email, role.
        db      : Injected MongoDB database.

    Returns:
        The created user's public info.
    """
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    user = {
        "_id": user_id,
        "username": request.username,
        "email": request.email,
        "role": request.role,
        "created_at": now,
        "updated_at": now,
    }
    try:
        await db.users.insert_one(user)
    except Exception as e:
        if "duplicate key" in str(e).lower() or "dup key" in str(e).lower():
            raise HTTPException(status_code=400, detail="Username or email already exists")
        raise HTTPException(status_code=500, detail=str(e))

    user["id"] = user["_id"]
    return user


# ────────────────────────────────────────────────────────────────
# Threads
# ────────────────────────────────────────────────────────────────

@router.post("/threads", response_model=ThreadResponse)
async def create_thread(
    request: CreateThreadRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Create a new conversation thread for a user."""
    # Verify user exists.
    user = await db.users.find_one({"_id": request.user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    thread_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    thread = {
        "_id": thread_id,
        "user_id": request.user_id,
        "title": request.title or "New conversation",
        "created_at": now,
        "updated_at": now,
    }
    await db.threads.insert_one(thread)
    thread["id"] = thread["_id"]
    return thread


@router.get("/threads/{thread_id}/messages", response_model=list[MessageResponse])
async def get_thread_messages(
    thread_id: uuid.UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Get all messages in a conversation thread, ordered chronologically."""
    thread = await db.threads.find_one({"_id": thread_id})
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    cursor = db.messages.find({"thread_id": thread_id}).sort("message_index", 1)
    messages = []
    async for msg in cursor:
        msg["id"] = msg["_id"]
        messages.append(msg)
    return messages


# ────────────────────────────────────────────────────────────────
# Chat — the main endpoint
# ────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Process a user message through the LangGraph agent.

    Flow:
        1. Create or reuse the conversation thread.
        2. Save the user's message.
        3. Build memory context (recent messages + rolling summary).
        4. Run the LangGraph agent (router → tool → answer).
        5. Save the assistant's response.
        6. Trigger rolling summary update if needed.
        7. Return the answer with sources.

    Args:
        request : ``ChatRequest`` with user_id, thread_id (optional), message.
        db      : Injected MongoDB database.

    Returns:
        ``ChatResponse`` with the answer, sources, and tool used.
    """
    # ── 1. Ensure user exists ───────────────────────────────────
    user = await db.users.find_one({"_id": request.user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # ── 2. Create or reuse thread ───────────────────────────────
    if request.thread_id:
        thread = await db.threads.find_one({"_id": request.thread_id})
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        thread_id = thread["_id"]
    else:
        thread_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        thread = {
            "_id": thread_id,
            "user_id": request.user_id,
            "title": "New conversation",
            "created_at": now,
            "updated_at": now,
        }
        await db.threads.insert_one(thread)

    # ── 3. Save user message ───────────────────────────────────
    msg_count = await get_message_count(db, thread_id)
    user_msg_id = uuid.uuid4()
    user_msg = {
        "_id": user_msg_id,
        "thread_id": thread_id,
        "role": "user",
        "content": request.message,
        "message_index": msg_count,
        "created_at": datetime.now(timezone.utc),
    }
    await db.messages.insert_one(user_msg)

    # ── 4. Build memory context ────────────────────────────────
    memory = await build_memory_context(db, thread_id)

    # ── 5. Run LangGraph agent ─────────────────────────────────
    graph = build_graph(db)
    initial_state: AgentState = {
        "messages": [HumanMessage(content=request.message)],
        "user_query": request.message,
        "thread_id": str(thread_id),
        "user_id": str(request.user_id),
        "recent_messages": memory["recent_messages"],
        "summary": memory["summary"],
        "retrieved_chunks": [],
        "tool_used": "",
        "final_answer": "",
    }

    result = await graph.ainvoke(initial_state)

    # ── 6. Save assistant response ─────────────────────────────
    assistant_msg_id = uuid.uuid4()
    assistant_msg = {
        "_id": assistant_msg_id,
        "thread_id": thread_id,
        "role": "assistant",
        "content": result["final_answer"],
        "tool_name": result.get("tool_used"),
        "message_index": msg_count + 1,
        "created_at": datetime.now(timezone.utc),
    }
    await db.messages.insert_one(assistant_msg)

    # ── 7. Update rolling summary if needed ────────────────────
    await update_rolling_summary(db, thread_id)

    # ── 8. Build response ──────────────────────────────────────
    sources = []
    for chunk in result.get("retrieved_chunks", []):
        sources.append(
            SourceChunk(
                document_id=uuid.UUID(str(chunk["document_id"])),
                chunk_index=chunk["chunk_index"],
                filename=chunk["filename"],
                source_page=chunk.get("source_page"),
                relevance_score=chunk.get("score"),
                snippet=chunk["content"][:300],
            )
        )

    return ChatResponse(
        thread_id=thread_id,
        answer=result["final_answer"],
        sources=sources,
        tool_used=result.get("tool_used", "unknown"),
    )


# ────────────────────────────────────────────────────────────────
# Document upload
# ────────────────────────────────────────────────────────────────

@router.get("/documents", response_model=list[DocumentStatusResponse])
async def list_documents(
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """List all ingested documents and their status."""
    cursor = db.documents.find().sort("created_at", -1)
    docs = []
    async for doc in cursor:
        doc["id"] = doc["_id"]
        docs.append(doc)
    return docs


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    user_id: uuid.UUID = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Upload a document for ingestion into the knowledge base.
    Restricted to admin users.

    Supported formats: PDF, DOCX, XLSX, TXT.

    Args:
        file    : The uploaded file.
        user_id : Uploader's user ID.
        db      : Injected MongoDB database.

    Returns:
        ``DocumentUploadResponse`` with document_id and status.
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id query parameter is required")

    # Verify user exists and is an admin
    user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only administrators can upload documents to the RAG knowledge base.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        doc = await ingest_document(db, file_bytes, file.filename, user_id)
        return DocumentUploadResponse(
            document_id=doc["id"],
            filename=doc["filename"],
            status=doc["status"],
            message=f"Document ingested successfully. {doc.get('total_chunks') or 0} chunks created.",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.get("/documents/{document_id}", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: uuid.UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Check the processing status of a document."""
    doc = await db.documents.find_one({"_id": document_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc["id"] = doc["_id"]
    return doc


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Delete a document and all of its associated chunks from the knowledge base.
    Restricted to admin users.
    """
    # Verify user exists and is admin
    user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only administrators can delete documents from the RAG knowledge base.")

    # Check if the document exists
    doc = await db.documents.find_one({"_id": document_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete related chunks
    await db.document_chunks.delete_many({"document_id": document_id})

    # Delete related ingestion manifests
    await db.ingestion_manifests.delete_many({"document_id": document_id})

    # Delete the document itself
    await db.documents.delete_one({"_id": document_id})

    return {"status": "success", "message": f"Document '{doc['filename']}' and its chunks were deleted successfully."}

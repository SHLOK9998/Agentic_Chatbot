"""
main.py
========
FastAPI application entry point.

Starts the server with::

    uvicorn main:app --reload

Or simply::

    python main.py
"""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from contextlib import asynccontextmanager

from app.api.routes import router
from app.config import settings
from app.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize MongoDB indexes
    await init_db()
    yield

# ── Create the FastAPI app ──────────────────────────────────────
app = FastAPI(
    title="RAG Chatbot",
    description=(
        "A production-ready RAG chatbot using LangGraph, MongoDB Atlas, "
        "hybrid retrieval (dense + full-text), RRF fusion, and Cohere reranking."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS middleware ─────────────────────────────────────────────
# Allow specified development origins when credentials are enabled.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Ensure CORS headers on unhandled 500s ──────────────────────
@app.middleware("http")
async def catch_exceptions(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        origin = request.headers.get("origin", "")
        headers = {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Credentials": "true"}
        return JSONResponse(status_code=500, content={"detail": str(e)}, headers=headers)

# ── Register API routes ────────────────────────────────────────
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint — confirms the API is running."""
    return {
        "service": "RAG Chatbot API",
        "version": "0.1.0",
        "docs": "/docs",
    }


# ── Run with ``python main.py`` ────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )

"""
services.embedding
===================
Thin wrapper around the Google Generative AI embedding endpoint.

Why a wrapper?
--------------
1. Centralises the API key and model name (from ``settings``).
2. Handles batching — embedding APIs have per-request token limits.
3. Makes it trivial to swap the provider later (OpenAI, Cohere, local model).

Usage::

    from app.services.embedding import embed_texts, embed_query
    vectors = await embed_texts(["chunk 1", "chunk 2"])
    query_vec = await embed_query("What is the leave policy?")
"""

import asyncio
from functools import lru_cache

import google.generativeai as genai

from app.config import settings


def _configure_genai() -> None:
    """
    Configure the ``google.generativeai`` SDK with our API key.
    Called once at module load.
    """
    genai.configure(api_key=settings.GOOGLE_API_KEY)


# Configure on first import.
_configure_genai()


async def embed_texts(
    texts: list[str],
    batch_size: int = 100,
) -> list[list[float]]:
    """
    Generate embeddings for a list of document chunks.

    Args:
        texts      : Plain-text chunks to embed.
        batch_size : How many texts to embed per API call (Google limit is ~100).

    Returns:
        A list of embedding vectors (each a ``list[float]``), one per input text.

    Notes:
        - Uses ``task_type="retrieval_document"`` so the model optimises for
          being *found* by a query (asymmetric embedding).
        - Runs the blocking SDK call in a thread pool so it doesn't block the
          async event loop.
    """
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        # google.generativeai is synchronous — run in thread pool.
        result = await asyncio.to_thread(
            genai.embed_content,
            model=settings.EMBEDDING_MODEL,
            content=batch,
            task_type="retrieval_document",
        )
        all_embeddings.extend(result["embedding"])

    return all_embeddings


async def embed_query(query: str) -> list[float]:
    """
    Generate an embedding for a single search query.

    Uses ``task_type="retrieval_query"`` (the asymmetric counterpart to
    ``retrieval_document``) so the model optimises for *finding* relevant
    documents.

    Args:
        query : The user's search query.

    Returns:
        A single embedding vector as ``list[float]``.
    """
    result = await asyncio.to_thread(
        genai.embed_content,
        model=settings.EMBEDDING_MODEL,
        content=query,
        task_type="retrieval_query",
    )
    return result["embedding"]

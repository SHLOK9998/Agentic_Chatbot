"""
services.retrieval
====================
Hybrid search + RRF fusion + Cohere reranking with MongoDB.

Pipeline: dense ($vectorSearch) + full-text ($text index search) → RRF fusion → rerank → return.
"""

import asyncio
from dataclasses import dataclass

import cohere
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import settings
from app.services.embedding import embed_query

_cohere_client: cohere.ClientV2 | None = None


def _get_cohere_client() -> cohere.ClientV2:
    """Return a singleton Cohere client."""
    global _cohere_client
    if _cohere_client is None:
        _cohere_client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)
    return _cohere_client


@dataclass
class RetrievedChunk:
    """A chunk that survived the retrieval pipeline."""
    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    source_page: str | None
    filename: str
    score: float = 0.0


async def _dense_search(db: AsyncIOMotorDatabase, query_embedding: list[float], top_k: int) -> list[dict]:
    """Cosine similarity search via MongoDB Atlas Vector Search."""
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": top_k * 10,
                "limit": top_k
            }
        },
        # Join with documents collection to verify completion status and get metadata
        {
            "$lookup": {
                "from": "documents",
                "localField": "document_id",
                "foreignField": "_id",
                "as": "doc"
            }
        },
        {"$unwind": "$doc"},
        {"$match": {"doc.status": "completed"}},
        {
            "$project": {
                "chunk_id": "$_id",
                "document_id": 1,
                "chunk_index": 1,
                "content": 1,
                "source_page": 1,
                "filename": "$doc.filename",
                "cosine_distance": {"$meta": "vectorSearchScore"}
            }
        }
    ]
    cursor = db.document_chunks.aggregate(pipeline)
    return [doc async for doc in cursor]


async def _fulltext_search(db: AsyncIOMotorDatabase, query: str, top_k: int) -> list[dict]:
    """MongoDB full-text search using native text indexing."""
    pipeline = [
        {
            "$match": {
                "$text": {"$search": query}
            }
        },
        {
            "$lookup": {
                "from": "documents",
                "localField": "document_id",
                "foreignField": "_id",
                "as": "doc"
            }
        },
        {"$unwind": "$doc"},
        {"$match": {"doc.status": "completed"}},
        {
            "$project": {
                "chunk_id": "$_id",
                "document_id": 1,
                "chunk_index": 1,
                "content": 1,
                "source_page": 1,
                "filename": "$doc.filename",
                "score": {"$meta": "textScore"}
            }
        },
        {"$sort": {"score": -1}},
        {"$limit": top_k}
    ]
    cursor = db.document_chunks.aggregate(pipeline)
    return [doc async for doc in cursor]


def _rrf_fuse(dense: list[dict], fts: list[dict], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion: ``score(d) = sum(1 / (k + rank_i))``."""
    scores: dict[str, float] = {}
    data: dict[str, dict] = {}
    for rank, item in enumerate(dense, 1):
        cid = str(item["chunk_id"])
        scores[cid] = scores.get(cid, 0) + 1 / (k + rank)
        data[cid] = item
    for rank, item in enumerate(fts, 1):
        cid = str(item["chunk_id"])
        scores[cid] = scores.get(cid, 0) + 1 / (k + rank)
        data[cid] = item
    sorted_ids = sorted(scores, key=lambda c: scores[c], reverse=True)
    result = []
    for cid in sorted_ids:
        d = data[cid]
        d["rrf_score"] = scores[cid]
        result.append(d)
    return result


async def _rerank(query: str, candidates: list[dict], top_n: int) -> list[dict]:
    """Cohere cross-encoder reranker on the fused candidates."""
    if not candidates:
        return []
    co = _get_cohere_client()
    docs = [c["content"] for c in candidates]
    resp = await asyncio.to_thread(
        co.rerank, model="rerank-v3.5", query=query,
        documents=docs, top_n=min(top_n, len(docs)),
    )
    reranked = []
    for r in resp.results:
        c = candidates[r.index]
        c["rerank_score"] = r.relevance_score
        reranked.append(c)
    return reranked


async def hybrid_retrieve(
    db: AsyncIOMotorDatabase, query: str,
    top_k: int | None = None, top_n: int | None = None,
) -> list[RetrievedChunk]:
    """
    Full hybrid retrieval: dense + FTS → RRF → rerank.

    Args:
        db    : Async MongoDB database.
        query : User's search query.
        top_k : Candidates per method (default from settings).
        top_n : Final chunks after reranking (default from settings).

    Returns:
        List of ``RetrievedChunk`` sorted by relevance.
    """
    top_k = top_k or settings.RETRIEVAL_TOP_K
    top_n = top_n or settings.RERANK_TOP_N
    qe = await embed_query(query)
    
    # Run dense and full-text searches in parallel.
    # Note: text search requires a text index to be created first (handled in init_db).
    dense, fts = await asyncio.gather(
        _dense_search(db, qe, top_k), _fulltext_search(db, query, top_k)
    )
    fused = _rrf_fuse(dense, fts)
    reranked = await _rerank(query, fused[:top_k], top_n)
    return [
        RetrievedChunk(
            chunk_id=str(i["chunk_id"]), document_id=str(i["document_id"]),
            chunk_index=i["chunk_index"], content=i["content"],
            source_page=i.get("source_page"), filename=i.get("filename", "unknown"),
            score=i.get("rerank_score", i.get("rrf_score", 0.0)),
        )
        for i in reranked
    ]

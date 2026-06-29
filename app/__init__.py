"""
app package
===========
Top-level package for the RAG chatbot application.
Sub-packages:
    - models   : SQLAlchemy ORM models (users, threads, messages, documents, chunks …)
    - schemas  : Pydantic request / response schemas for the API layer
    - services : Business-logic modules (ingestion, retrieval, memory, embedding)
    - agent    : LangGraph agent graph, state definition, and tool implementations
    - api      : FastAPI route definitions
"""

"""
agent package
==============
LangGraph-based agent with two tools:
    1. ``rag_search``   — retrieves from ingested documents.
    2. ``general_chat`` — falls back to plain LLM when RAG isn't relevant.
"""

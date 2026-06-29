"""
agent.tools
=============
LangGraph node functions that act as "tools" for the agent.

Two tools are implemented:

1. **rag_search** — Runs hybrid retrieval against ingested documents,
   packs the top chunks into a prompt, and generates a grounded answer.

2. **general_chat** — Falls back to a plain LLM response with a system
   prompt when the question is unrelated to the knowledge base.

The **router** node decides which tool to use based on the LLM's
assessment of whether the question is answerable from the documents.
"""

from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agent.state import AgentState
from app.config import settings
from app.services.retrieval import hybrid_retrieve


def _get_groq_llm() -> ChatGroq:
    """Create a configured LLM instance using Groq."""
    return ChatGroq(
        model=settings.GROQ_MODEL_NAME,
        groq_api_key=settings.GROQ_API_KEY,
        temperature=settings.LLM_TEMPERATURE,
    )


def _get_gemini_llm() -> ChatGoogleGenerativeAI:
    """Create a configured LLM instance using Gemini."""
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL_NAME,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=settings.LLM_TEMPERATURE,
    )


# ────────────────────────────────────────────────────────────────
# Router node — decides RAG vs. general chat
# ────────────────────────────────────────────────────────────────

async def router_node(state: AgentState, db: AsyncIOMotorDatabase) -> dict:
    """
    Decide whether the user's question should be answered via RAG or
    general chat.

    Strategy:
        1. Ask the LLM (fast, cheap call) if the question is likely
           about uploaded documents / company knowledge.
        2. If yes → route to ``rag_search``.
        3. If no  → route to ``general_chat``.

    Args:
        state : Current agent state.
        db    : Async MongoDB database.

    Returns:
        Updated state with ``tool_used`` set.
    """
    llm = _get_groq_llm()

    # Build context for the router decision.
    routing_prompt = f"""You are a routing assistant. Based on the user's question and
conversation context, decide if this question should be answered using
uploaded knowledge-base documents (RAG) or general conversation.

Conversation summary: {state.get('summary', 'None')}
Recent messages: {state.get('recent_messages', 'None')}
User question: {state['user_query']}

Reply with EXACTLY one word:
- "RAG" if the question is about specific documents, company policies,
  data, or factual information that would be in uploaded files.
- "GENERAL" if the question is casual conversation, general knowledge,
  greetings, or not related to any uploaded documents.

Your answer (one word):"""

    response = await llm.ainvoke(routing_prompt)
    decision = response.content.strip().upper()

    tool = "rag_search" if "RAG" in decision else "general_chat"
    return {"tool_used": tool}


# ────────────────────────────────────────────────────────────────
# RAG Search tool
# ────────────────────────────────────────────────────────────────

async def rag_search_node(state: AgentState, db: AsyncIOMotorDatabase) -> dict:
    """
    Retrieve relevant chunks and generate a grounded answer.

    Steps:
        1. Run hybrid retrieval (dense + FTS → RRF → rerank).
        2. Pack the top chunks into a context-aware prompt.
        3. Generate an answer with source citations.

    Args:
        state : Current agent state.
        db    : Async MongoDB database.

    Returns:
        Updated state with ``retrieved_chunks`` and ``final_answer``.
    """
    query = state["user_query"]

    # ── Retrieve ────────────────────────────────────────────────
    chunks = await hybrid_retrieve(db, query)

    if not chunks:
        # No relevant documents found — fall back to general chat.
        return {
            "retrieved_chunks": [],
            "tool_used": "general_chat",
            "final_answer": "",
        }

    # ── Build evidence context ──────────────────────────────────
    evidence_parts = []
    chunk_dicts = []
    for i, chunk in enumerate(chunks, 1):
        source_label = f"[Source {i}: {chunk.filename}"
        if chunk.source_page:
            source_label += f", Page/Sheet: {chunk.source_page}"
        source_label += f", Relevance: {chunk.score:.3f}]"
        evidence_parts.append(f"{source_label}\n{chunk.content}")
        chunk_dicts.append({
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "source_page": chunk.source_page,
            "filename": chunk.filename,
            "score": chunk.score,
        })

    evidence_text = "\n\n---\n\n".join(evidence_parts)

    # ── Generate answer ─────────────────────────────────────────
    llm = _get_gemini_llm()
    prompt = f"""You are a helpful assistant that answers questions based on the
provided document evidence. Always base your answer on the evidence below.
If the evidence doesn't contain enough information, say so clearly.

Conversation summary: {state.get('summary', 'No summary available.')}

Recent conversation:
{state.get('recent_messages', 'No recent messages.')}

Document evidence:
{evidence_text}

User question: {query}

Instructions:
- Answer the question based on the document evidence above.
- Reference specific sources when possible (e.g., "According to [Source 1]...").
- If the evidence is insufficient, acknowledge what you found and what's missing.
- Be concise but thorough.

Your answer:"""

    response = await llm.ainvoke(prompt)

    return {
        "retrieved_chunks": chunk_dicts,
        "final_answer": response.content,
        "messages": [AIMessage(content=response.content)],
    }


# ────────────────────────────────────────────────────────────────
# General Chat tool (fallback)
# ────────────────────────────────────────────────────────────────

async def general_chat_node(state: AgentState, db: AsyncIOMotorDatabase) -> dict:
    """
    Generate a response using the LLM without RAG context.

    This is the fallback when the router decides the question is not
    related to the knowledge base.  Uses a system prompt and the
    conversation memory.

    Args:
        state : Current agent state.
        db    : Async database session (unused, kept for consistent interface).

    Returns:
        Updated state with ``final_answer`` and empty ``retrieved_chunks``.
    """
    llm = _get_groq_llm()

    prompt = f"""You are a helpful, friendly AI assistant. You are having a
conversation with a user. Use the conversation context below to maintain
continuity.

Conversation summary: {state.get('summary', 'No summary available.')}

Recent conversation:
{state.get('recent_messages', 'No recent messages.')}

User message: {state['user_query']}

Instructions:
- Be helpful, clear, and conversational.
- If the user asks about something that might be in their uploaded documents,
  suggest they upload relevant files or rephrase the question.
- Keep responses concise but complete.

Your response:"""

    response = await llm.ainvoke(prompt)

    return {
        "retrieved_chunks": [],
        "final_answer": response.content,
        "messages": [AIMessage(content=response.content)],
    }

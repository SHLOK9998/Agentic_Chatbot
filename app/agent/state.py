"""
agent.state
=============
TypedDict that defines the LangGraph agent state.

The state flows through every node in the graph.  Keeping it as a
simple TypedDict (not a Pydantic model) is the LangGraph convention
and makes the graph JSON-serialisable.
"""

from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    Shared state that passes through the LangGraph nodes.

    Attributes:
        messages          : LangChain message history for the current turn.
                            Uses ``add_messages`` reducer so each node can
                            append without overwriting.
        user_query        : The raw user question (before any rewriting).
        thread_id         : UUID string of the conversation thread.
        user_id           : UUID string of the authenticated user.
        recent_messages   : Formatted string of last N messages (memory).
        summary           : Rolling summary of the conversation (memory).
        retrieved_chunks  : List of dicts from the retrieval service.
        tool_used         : Which tool was chosen (``rag_search`` or ``general_chat``).
        final_answer      : The generated answer to return to the user.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    user_query: str
    thread_id: str
    user_id: str
    recent_messages: str
    summary: str
    retrieved_chunks: list[dict]
    tool_used: str
    final_answer: str

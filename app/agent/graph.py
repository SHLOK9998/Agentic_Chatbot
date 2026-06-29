"""
agent.graph
=============
LangGraph state graph wiring.

The graph has three nodes and conditional routing::

    ┌─────────┐
    │  START  │
    └────┬────┘
         │
    ┌────▼────┐
    │ router  │  ← decides RAG vs. general chat
    └────┬────┘
         │
    ┌────┴─────────────┐
    │                  │
    ▼                  ▼
  rag_search     general_chat
    │                  │
    └────┬─────────────┘
         │
    ┌────▼────┐
    │   END   │
    └─────────┘

Why LangGraph?
--------------
Even though this is only 2 tools today, LangGraph makes it trivial to
add more tools later (web search, SQL query, API call, etc.) without
restructuring the code.  Each tool is just a new node + edge.

Usage::

    from app.agent.graph import build_graph
    graph = build_graph(db_session)
    result = await graph.ainvoke(initial_state)
"""

from functools import partial

from langgraph.graph import StateGraph, END

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agent.state import AgentState
from app.agent.tools import router_node, rag_search_node, general_chat_node


def _route_decision(state: AgentState) -> str:
    """
    Conditional edge function: read ``tool_used`` from the state and
    route to the corresponding node.

    Returns:
        Node name: ``"rag_search"`` or ``"general_chat"``.
    """
    return state.get("tool_used", "general_chat")


def build_graph(db: AsyncIOMotorDatabase) -> StateGraph:
    """
    Build and compile the LangGraph state graph.

    The ``db`` session is injected into each node via ``functools.partial``
    so the nodes don't need to know how to obtain a session — they just
    receive it as an argument.

    Args:
        db : Active async database session for the current request.

    Returns:
        A compiled ``StateGraph`` ready for ``.ainvoke()``.
    """
    graph = StateGraph(AgentState)

    # ── Register nodes ──────────────────────────────────────────
    # ``partial`` binds the ``db`` argument so each node function
    # receives ``(state, db)`` but LangGraph only passes ``state``.
    graph.add_node("router", partial(router_node, db=db))
    graph.add_node("rag_search", partial(rag_search_node, db=db))
    graph.add_node("general_chat", partial(general_chat_node, db=db))

    # ── Wire edges ──────────────────────────────────────────────
    graph.set_entry_point("router")

    # Conditional edge from router → tool node based on state.tool_used.
    graph.add_conditional_edges(
        "router",
        _route_decision,
        {
            "rag_search": "rag_search",
            "general_chat": "general_chat",
        },
    )

    # Both tool nodes terminate the graph.
    graph.add_edge("rag_search", END)
    graph.add_edge("general_chat", END)

    return graph.compile()

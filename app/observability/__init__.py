"""Langfuse client and trace_id helpers.

Constitution Principle V: every agent decision is logged to Langfuse with
inputs, retrieved sources, agent state, and output. Every ``DefenderResponse``
carries a ``trace_id`` referencing a replayable Langfuse trace.
"""

from app.observability.langfuse_client import (
    NullLangfuseClient,
    TraceContext,
    get_langfuse_client,
)

__all__ = ["NullLangfuseClient", "TraceContext", "get_langfuse_client"]

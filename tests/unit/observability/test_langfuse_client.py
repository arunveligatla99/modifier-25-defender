"""Unit tests for app.observability.langfuse_client (null-client path)."""

from __future__ import annotations

from app.observability.langfuse_client import (
    NullLangfuseClient,
    TraceContext,
    trace_session,
)


class TestNullLangfuseClient:
    def test_start_trace_returns_local_id(self) -> None:
        c = NullLangfuseClient()
        ctx = c.start_trace(name="analyze", metadata={"encounter_id": "enc-1"})
        assert isinstance(ctx, TraceContext)
        assert ctx.trace_id.startswith("lf_t_local_")

    def test_log_span_appends(self) -> None:
        c = NullLangfuseClient()
        ctx = c.start_trace(name="x", metadata={})
        c.log_span(ctx, "parser", inputs={"note": "x"}, outputs={"parsed": True})
        c.log_span(ctx, "analyzer", inputs={}, outputs={})
        assert len(ctx.spans) == 2
        assert ctx.spans[0][0] == "parser"

    def test_finalize_returns_trace_id(self) -> None:
        c = NullLangfuseClient()
        ctx = c.start_trace(name="x", metadata={})
        assert c.finalize_trace(ctx) == ctx.trace_id


class TestTraceSessionContext:
    def test_yields_trace_and_finalizes(self) -> None:
        c = NullLangfuseClient()
        with trace_session(c, name="analyze") as trace:
            assert trace.trace_id.startswith("lf_t_local_")
            c.log_span(trace, "parser", {}, {})
        # finalize_trace was called as part of the context exit
        assert trace.spans  # spans recorded before exit

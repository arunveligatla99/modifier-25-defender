"""Langfuse client wrapper with a null-object fallback for offline runs.

Implements Constitution Principle V (Full Auditability and Replay). Every
``DefenderResponse`` carries a ``trace_id`` returned by ``finalize_trace``.
When Langfuse credentials are not configured (e.g., a unit test or a CI run
without secrets), a :class:`NullLangfuseClient` returns synthetic trace IDs
without making network calls so the rest of the system continues to work.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.infra.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class TraceContext:
    """Lightweight in-process record of a trace and its spans.

    The Langfuse SDK records the same shape on the server side; this dataclass
    mirrors it locally so the agent code path is unchanged when running
    against the null client.
    """

    trace_id: str
    spans: list[tuple[str, dict[str, Any]]] = field(default_factory=list)


class _LangfuseClientLike(Protocol):
    """Protocol matching the subset of the Langfuse SDK we use."""

    def start_trace(self, name: str, metadata: dict[str, Any]) -> TraceContext: ...
    def log_span(
        self,
        trace: TraceContext,
        name: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
    ) -> None: ...
    def finalize_trace(self, trace: TraceContext) -> str: ...


class NullLangfuseClient:
    """Offline fallback used when Langfuse credentials are not configured.

    Generates synthetic trace IDs of the form ``lf_t_local_<uuid>`` and stores
    spans in-memory only. Useful for unit tests and CI runs without secrets.
    """

    def start_trace(self, name: str, metadata: dict[str, Any]) -> TraceContext:
        """Begin a synthetic trace and return its context."""
        trace_id = f"lf_t_local_{uuid.uuid4().hex}"
        logger.debug("NullLangfuseClient: start_trace name=%s trace_id=%s", name, trace_id)
        return TraceContext(trace_id=trace_id)

    def log_span(
        self,
        trace: TraceContext,
        name: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
    ) -> None:
        """Append the span to the trace's in-memory record."""
        trace.spans.append((name, {"inputs": inputs, "outputs": outputs}))

    def finalize_trace(self, trace: TraceContext) -> str:
        """Return the trace ID. The null client has nothing to flush."""
        logger.debug("NullLangfuseClient: finalize_trace trace_id=%s", trace.trace_id)
        return trace.trace_id


@contextmanager
def trace_session(
    client: _LangfuseClientLike, name: str, metadata: dict[str, Any] | None = None
) -> Iterator[TraceContext]:
    """Context manager that starts and finalizes a trace.

    Args:
        client: Any client matching :class:`_LangfuseClientLike`.
        name: Trace name (typically the API endpoint).
        metadata: Optional metadata such as ``encounter_id``.

    Yields:
        The active :class:`TraceContext` for the duration of the block.
    """
    trace = client.start_trace(name=name, metadata=metadata or {})
    try:
        yield trace
    finally:
        client.finalize_trace(trace)


def get_langfuse_client() -> _LangfuseClientLike:
    """Return a Langfuse client, falling back to :class:`NullLangfuseClient`.

    The real SDK is imported lazily so the null path does not require the
    package to be installed. If credentials are missing, the null client is
    returned even when the SDK is available, which keeps unit tests and CI
    runs without secrets fully self-contained.
    """
    settings = get_settings()
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return NullLangfuseClient()

    try:
        from langfuse import Langfuse
    except ImportError:
        logger.warning("langfuse SDK not installed; falling back to NullLangfuseClient")
        return NullLangfuseClient()

    sdk: Any = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )

    # The Langfuse Python SDK has shifted between major versions; wrap each
    # call in a defensive ``getattr`` + try block so a server-side or
    # SDK-version surprise degrades to the null path rather than blowing up
    # in production. Constitution Principle V says every response must carry
    # a trace_id; that is preserved by the null fallback when this adapter
    # cannot serve it.
    class _Adapter:
        def start_trace(self, name: str, metadata: dict[str, Any]) -> TraceContext:
            try:
                trace_fn = getattr(sdk, "trace", None) or getattr(sdk, "start_trace", None)
                if trace_fn is None:
                    raise AttributeError("langfuse SDK exposes no trace() or start_trace()")
                handle = trace_fn(name=name, metadata=metadata)
                trace_id = getattr(handle, "id", None) or getattr(handle, "trace_id", None)
                if not trace_id:
                    raise AttributeError("langfuse trace handle has no id")
                return TraceContext(trace_id=str(trace_id))
            except Exception as exc:  # pragma: no cover - exercised by integration only
                logger.warning("Langfuse start_trace failed (%s); using null trace", exc)
                return NullLangfuseClient().start_trace(name=name, metadata=metadata)

        def log_span(
            self,
            trace: TraceContext,
            name: str,
            inputs: dict[str, Any],
            outputs: dict[str, Any],
        ) -> None:
            try:
                span_fn = getattr(sdk, "span", None) or getattr(sdk, "log_span", None)
                if span_fn is None:
                    raise AttributeError("langfuse SDK exposes no span() or log_span()")
                span_fn(
                    trace_id=trace.trace_id,
                    name=name,
                    input=inputs,
                    output=outputs,
                )
            except Exception as exc:  # pragma: no cover - exercised by integration only
                logger.warning("Langfuse log_span failed (%s); ignoring", exc)

        def finalize_trace(self, trace: TraceContext) -> str:
            try:
                flush = getattr(sdk, "flush", None)
                if flush is not None:
                    flush()
            except Exception as exc:  # pragma: no cover - exercised by integration only
                logger.warning("Langfuse flush failed (%s); ignoring", exc)
            return trace.trace_id

    return _Adapter()

"""Orchestrator wiring (T148).

The orchestrator is the only place where the synthesis-side agents
(parser, analyzer, drafter) and the verification side (compliance_guard)
meet. The import-graph lint classifies this package as "neutral" so
imports across the boundary are allowed here, and only here.

For v1, orchestration is a synchronous function: parser -> analyzer ->
compliance_guard. The Remediation Drafter is conditional on overall in
{WEAK, FAIL} and is wired in T203 (US2). LangGraph's checkpoint
persistence is deferred; v1 ships without it because the orchestrator's
straight-line composition does not benefit from a graph runtime, and the
trace_id from the Langfuse client already supports replay against the
current code (see ``make replay``).
"""

from app.agents.orchestrator.graph import OrchestratorError, orchestrate_request

__all__ = ["OrchestratorError", "orchestrate_request"]

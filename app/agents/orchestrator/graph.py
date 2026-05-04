"""Synchronous orchestrator wiring parser -> analyzer -> compliance guard.

Lives at the "neutral" boundary in ``app/agents/orchestrator/``. The
import-graph lint allows this package to import from both the synthesis
side and the verification side; that boundary-crossing is the entire
purpose of this module.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Protocol

from app.agents.analyzer import AnalyzerAgent
from app.agents.compliance_guard import ComplianceGuard, verify_response
from app.agents.parser import ParserAgent
from app.observability.langfuse_client import (
    NullLangfuseClient,
    TraceContext,
    trace_session,
)
from app.schemas.api import DefenderRequest, DefenderResponse
from app.schemas.assessment import DefensibilityAssessment
from app.schemas.parser import ParsedEncounter
from app.schemas.remediation import RemediationSuggestion

logger = logging.getLogger(__name__)


class OrchestratorError(RuntimeError):
    """Raised when an upstream agent fails in a way the orchestrator cannot recover from."""


class _LangfuseLike(Protocol):
    """Subset of the Langfuse client we need for trace_session."""

    def start_trace(self, name: str, metadata: dict[str, object]) -> TraceContext: ...
    def log_span(
        self,
        trace: TraceContext,
        name: str,
        inputs: dict[str, object],
        outputs: dict[str, object],
    ) -> None: ...
    def finalize_trace(self, trace: TraceContext) -> str: ...


def orchestrate_request(
    request: DefenderRequest,
    *,
    parser: ParserAgent,
    analyzer: AnalyzerAgent,
    guard: ComplianceGuard,
    policy_text_index: dict[str, str],
    drafter: object | None = None,
    langfuse: _LangfuseLike | None = None,
) -> DefenderResponse:
    """Run the full request pipeline and return a :class:`DefenderResponse`.

    Args:
        request: Validated request payload.
        parser: Documentation Parser agent (EPIC-003).
        analyzer: Defensibility Analyzer agent (EPIC-004).
        guard: Compliance Guard (EPIC-005).
        policy_text_index: Map from chunk_id to chunk text used by the
            guard to resolve policy citations.
        drafter: Optional Remediation Drafter (EPIC-006/US2). When ``None``
            the orchestrator skips the drafter entirely; this is the v1
            US1 path.
        langfuse: Optional Langfuse client; defaults to the null client so
            ``trace_id`` is always present (Constitution Principle V).

    Returns:
        A :class:`DefenderResponse` with ``compliance_status`` set by the
        guard.
    """
    client = langfuse or NullLangfuseClient()
    with trace_session(
        client,
        name="analyze",
        metadata={
            "encounter_id": request.encounter_id,
            "em_code": request.em_code,
            "procedure_code": request.procedure_code,
            "site": request.site or "none",
        },
    ) as trace:
        parsed = parser.parse(request.note_text)
        client.log_span(
            trace,
            "parser",
            inputs={"note_text_len": len(request.note_text)},
            outputs={"fields_with_spans": _field_counts(parsed)},
        )

        assessment = analyzer.score(
            parsed,
            em_code=request.em_code,
            procedure_code=request.procedure_code,
            site=request.site,
        )
        client.log_span(
            trace,
            "analyzer",
            inputs={"em_code": request.em_code, "procedure_code": request.procedure_code},
            outputs={"overall": assessment.overall},
        )

        remediations: list[RemediationSuggestion] = []
        if drafter is not None and assessment.overall in {"WEAK", "FAIL"}:
            remediations = list(_invoke_drafter(drafter, parsed, assessment))
            client.log_span(
                trace,
                "drafter",
                inputs={"overall": assessment.overall},
                outputs={"remediation_count": len(remediations)},
            )

        provisional = DefenderResponse(
            encounter_id=request.encounter_id,
            parsed=parsed,
            assessment=assessment,
            remediations=remediations,
            compliance_status="PASSED",  # provisional, will be set by guard
            blocked_reasons=None,
            trace_id=trace.trace_id,
        )
        verified = verify_response(
            response=provisional,
            parsed=parsed,
            policy_text_index=policy_text_index,
            verifier=guard.verifier,
            threshold=guard.threshold,
        )
        client.log_span(
            trace,
            "compliance_guard",
            inputs={"citation_count": _count_citations(assessment, remediations)},
            outputs={"compliance_status": verified.compliance_status},
        )
        return verified


def _field_counts(parsed: ParsedEncounter) -> dict[str, int]:
    return {
        "cc": len(parsed.cc),
        "hpi": len(parsed.hpi),
        "exam_findings": len(parsed.exam_findings),
        "mdm": len(parsed.mdm),
        "procedure_note": len(parsed.procedure_note),
        "ambiguous_segments": len(parsed.ambiguous_segments),
    }


def _count_citations(
    assessment: DefensibilityAssessment | None,
    remediations: Iterable[RemediationSuggestion],
) -> int:
    n = 0
    if assessment is not None:
        n += len(assessment.criteria.distinct_cc.evidence)
        n += len(assessment.criteria.separate_exam.evidence)
        n += len(assessment.criteria.independent_mdm.evidence)
        n += len(assessment.criteria.site_specificity.evidence)
    for r in remediations:
        n += len(r.motivation)
    return n


def _invoke_drafter(
    drafter: object,
    parsed: ParsedEncounter,
    assessment: DefensibilityAssessment,
) -> list[RemediationSuggestion]:
    """Call the optional drafter via duck-typed ``draft`` method.

    The drafter contract is finalized in EPIC-006 (US2). For v1 US1 the
    drafter is None and this branch is not exercised. When wired, a
    ``draft(parsed, assessment) -> list[RemediationSuggestion]`` method is
    expected.
    """
    if not hasattr(drafter, "draft"):
        raise OrchestratorError(
            "drafter argument does not expose draft(parsed, assessment); "
            "see EPIC-006 spec for the contract"
        )
    result = drafter.draft(parsed, assessment)
    if not isinstance(result, list):
        raise OrchestratorError("drafter.draft returned a non-list")
    return result

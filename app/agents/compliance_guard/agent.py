"""Compliance Guard agent.

For every :class:`Citation` produced by the synthesis side, runs NLI
between the cited span (premise) and the agent's rationale (hypothesis).
If any citation falls below the entailment threshold, the response is
demoted to BLOCKED with structured ``blocked_reasons`` (Q2 resolution:
v1 is two-state PASSED/BLOCKED, no DEGRADED).

Constitution Principle II requires this module to be a separate concern
from synthesis. The architectural separation is enforced by the
import-graph lint in ``scripts/check_imports.py`` (T138).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.agents.compliance_guard.nli import NLIVerifier
from app.schemas.api import DefenderResponse
from app.schemas.assessment import DefensibilityAssessment
from app.schemas.parser import ParsedEncounter
from app.schemas.remediation import RemediationSuggestion
from app.schemas.text import Citation

logger = logging.getLogger(__name__)

NLI_THRESHOLD: float = 0.75
"""Entailment probability at or above which a citation is considered verified."""


@dataclass(frozen=True)
class VerificationFailure:
    """One failed citation, ready to be rendered as a blocked_reasons entry."""

    location: str  # e.g. "criterion=independent_mdm" or "remediation=independent_mdm"
    rationale: str
    cited_span: str
    entailment_score: float

    def render(self) -> str:
        """Format the failure as a human-readable line for ``blocked_reasons``."""
        score_str = f"{self.entailment_score:.2f}"
        return (
            f"{self.location}: NLI entailment {score_str} below threshold "
            f"{NLI_THRESHOLD:.2f}; claim '{self.rationale}' not entailed by cited "
            f"span '{_truncate(self.cited_span, 200)}'."
        )


@dataclass(frozen=True)
class GuardOutcome:
    """Output of the Compliance Guard.

    Attributes:
        verified: True when every citation passed entailment.
        failures: List of :class:`VerificationFailure` entries; empty when
            ``verified`` is True.
        citation_count: Total number of citations evaluated.
    """

    verified: bool
    failures: list[VerificationFailure] = field(default_factory=list)
    citation_count: int = 0

    def blocked_reasons(self) -> list[str]:
        """Return the structured ``blocked_reasons`` list for the API response."""
        return [f.render() for f in self.failures]


@dataclass(frozen=True)
class ComplianceGuard:
    """Wraps an NLI verifier with a fixed entailment threshold."""

    verifier: NLIVerifier
    threshold: float = NLI_THRESHOLD

    def verify(
        self,
        *,
        assessment: DefensibilityAssessment | None,
        remediations: Iterable[RemediationSuggestion],
        parsed: ParsedEncounter,
        policy_text_index: dict[str, str],
    ) -> GuardOutcome:
        """Run NLI verification on every citation in the response.

        Args:
            assessment: The four-criterion assessment, or ``None`` when the
                upstream synthesis path did not produce one.
            remediations: Remediation suggestions (each carries motivation
                citations).
            parsed: Parsed encounter, used to resolve encounter spans.
            policy_text_index: Mapping from chunk_id to chunk text, used to
                resolve policy spans.

        Returns:
            A :class:`GuardOutcome` summarizing pass/fail per citation.
        """
        return verify_collection(
            assessment=assessment,
            remediations=list(remediations),
            parsed=parsed,
            policy_text_index=policy_text_index,
            verifier=self.verifier,
            threshold=self.threshold,
        )


def verify_collection(
    *,
    assessment: DefensibilityAssessment | None,
    remediations: list[RemediationSuggestion],
    parsed: ParsedEncounter,
    policy_text_index: dict[str, str],
    verifier: NLIVerifier,
    threshold: float = NLI_THRESHOLD,
) -> GuardOutcome:
    """Functional implementation of :meth:`ComplianceGuard.verify`."""
    failures: list[VerificationFailure] = []
    count = 0

    if assessment is not None:
        for criterion_name, score in (
            ("distinct_cc", assessment.criteria.distinct_cc),
            ("separate_exam", assessment.criteria.separate_exam),
            ("independent_mdm", assessment.criteria.independent_mdm),
            ("site_specificity", assessment.criteria.site_specificity),
        ):
            if not score.evidence:
                # Schema enforces non-empty evidence, but defend in depth.
                failures.append(
                    VerificationFailure(
                        location=f"criterion={criterion_name}",
                        rationale="(none)",
                        cited_span="(none)",
                        entailment_score=0.0,
                    )
                )
                continue
            for citation in score.evidence:
                count += 1
                failure = _verify_citation(
                    citation=citation,
                    location=f"criterion={criterion_name}",
                    parsed=parsed,
                    policy_text_index=policy_text_index,
                    verifier=verifier,
                    threshold=threshold,
                )
                if failure is not None:
                    failures.append(failure)

    for suggestion in remediations:
        for citation in suggestion.motivation:
            count += 1
            failure = _verify_citation(
                citation=citation,
                location=f"remediation={suggestion.criterion}",
                parsed=parsed,
                policy_text_index=policy_text_index,
                verifier=verifier,
                threshold=threshold,
            )
            if failure is not None:
                failures.append(failure)

    return GuardOutcome(
        verified=not failures,
        failures=failures,
        citation_count=count,
    )


def verify_response(
    *,
    response: DefenderResponse,
    parsed: ParsedEncounter,
    policy_text_index: dict[str, str],
    verifier: NLIVerifier,
    threshold: float = NLI_THRESHOLD,
) -> DefenderResponse:
    """Apply :class:`ComplianceGuard` to a response, returning a new response.

    Per Q2 resolution: any verification failure demotes the response to
    BLOCKED. ``assessment`` and ``remediations`` are cleared on BLOCKED to
    avoid leaking unverified content into the UI; ``parsed`` is preserved
    so the coder can see how their note was interpreted.
    """
    outcome = verify_collection(
        assessment=response.assessment,
        remediations=response.remediations,
        parsed=parsed,
        policy_text_index=policy_text_index,
        verifier=verifier,
        threshold=threshold,
    )
    if outcome.verified:
        return response.model_copy(update={"compliance_status": "PASSED", "blocked_reasons": None})

    return response.model_copy(
        update={
            "assessment": None,
            "remediations": [],
            "compliance_status": "BLOCKED",
            "blocked_reasons": outcome.blocked_reasons(),
        }
    )


def _verify_citation(
    *,
    citation: Citation,
    location: str,
    parsed: ParsedEncounter,
    policy_text_index: dict[str, str],
    verifier: NLIVerifier,
    threshold: float,
) -> VerificationFailure | None:
    """Verify one citation; return a :class:`VerificationFailure` or ``None``.

    Per spec R4 (5a path): NLI verifies ``citation.entailed_paraphrase``
    (the LLM-emitted content paraphrase of the cited span), NOT
    ``citation.rationale`` (which is interpretive and free-form).
    """
    premise = _premise_for(citation, parsed=parsed, policy_text_index=policy_text_index)
    if premise is None:
        return VerificationFailure(
            location=location,
            rationale=citation.entailed_paraphrase,
            cited_span=citation.span.text,
            entailment_score=0.0,
        )
    hypothesis = citation.entailed_paraphrase
    score = verifier.entailment_probability(premise, hypothesis)
    if score >= threshold:
        return None
    return VerificationFailure(
        location=location,
        rationale=hypothesis,
        cited_span=citation.span.text,
        entailment_score=float(score),
    )


def _premise_for(
    citation: Citation,
    *,
    parsed: ParsedEncounter,
    policy_text_index: dict[str, str],
) -> str | None:
    """Resolve the premise text the citation refers to.

    For ``source_type == "encounter"``, the premise is the cited span text
    (the schema invariant guarantees this matches the source note).
    For ``source_type == "policy"``, the premise is looked up in
    ``policy_text_index`` by ``policy_id``; an unknown ``policy_id``
    returns ``None`` (treated as a verification failure).
    """
    if citation.source_type == "encounter":
        return citation.span.text
    if not citation.policy_id:
        return None
    return policy_text_index.get(citation.policy_id)


def _truncate(text: str, max_chars: int) -> str:
    """Truncate text for inclusion in a ``blocked_reasons`` line."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."

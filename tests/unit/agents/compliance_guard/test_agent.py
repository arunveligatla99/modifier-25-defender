"""Unit tests for the Compliance Guard agent (EPIC-005)."""

from __future__ import annotations

from app.agents.compliance_guard import (
    NLI_THRESHOLD,
    ComplianceGuard,
    NLIStub,
    verify_response,
)
from app.agents.compliance_guard.agent import VerificationFailure, _truncate
from app.schemas.api import DefenderResponse
from app.schemas.assessment import (
    CriteriaMap,
    CriterionScore,
    DefensibilityAssessment,
    Verdict,
)
from app.schemas.parser import ParsedEncounter
from app.schemas.remediation import RemediationSuggestion
from app.schemas.text import Citation, TextSpan


def _enc_citation(
    text: str,
    rationale: str = "explanation",
    *,
    entailed_paraphrase: str | None = None,
) -> Citation:
    return Citation(
        source_type="encounter",
        span=TextSpan(text=text, start_char=0, end_char=len(text)),
        rationale=rationale,
        entailed_paraphrase=entailed_paraphrase or text,
    )


def _policy_citation(
    policy_id: str,
    span_text: str,
    rationale: str,
    *,
    entailed_paraphrase: str | None = None,
) -> Citation:
    return Citation(
        source_type="policy",
        span=TextSpan(text=span_text, start_char=0, end_char=len(span_text)),
        policy_id=policy_id,
        rationale=rationale,
        entailed_paraphrase=entailed_paraphrase or span_text,
    )


def _score(verdict: Verdict, evidence: list[Citation]) -> CriterionScore:
    return CriterionScore(verdict=verdict, confidence=0.9, evidence=evidence)


def _assessment(
    cc: list[Citation],
    se: list[Citation],
    mdm: list[Citation],
    ss: list[Citation],
    *,
    overall: Verdict = "PASS",
) -> DefensibilityAssessment:
    return DefensibilityAssessment(
        overall=overall,
        criteria=CriteriaMap(
            distinct_cc=_score("PASS", cc),
            separate_exam=_score("PASS", se),
            independent_mdm=_score("PASS", mdm),
            site_specificity=_score("PASS", ss),
        ),
    )


def _response(assessment: DefensibilityAssessment | None) -> DefenderResponse:
    return DefenderResponse(
        encounter_id="enc-1",
        parsed=ParsedEncounter(),
        assessment=assessment,
        remediations=[],
        compliance_status="PASSED",
        blocked_reasons=None,
        trace_id="lf_t_local_1",
    )


class TestComplianceGuardVerify:
    def test_all_entailed_returns_verified(self) -> None:
        c = _enc_citation("thick painful nails", rationale="CC names a procedure indication")
        a = _assessment([c], [c], [c], [c])
        guard = ComplianceGuard(verifier=NLIStub(default=0.99))
        outcome = guard.verify(
            assessment=a,
            remediations=[],
            parsed=ParsedEncounter(),
            policy_text_index={},
        )
        assert outcome.verified
        assert outcome.failures == []
        assert outcome.citation_count == 4

    def test_below_threshold_yields_failure(self) -> None:
        c = _enc_citation("nail debridement", rationale="MDM addresses separate problem")
        a = _assessment([c], [c], [c], [c])
        guard = ComplianceGuard(verifier=NLIStub(default=0.50))
        outcome = guard.verify(
            assessment=a,
            remediations=[],
            parsed=ParsedEncounter(),
            policy_text_index={},
        )
        assert not outcome.verified
        assert len(outcome.failures) == 4

    def test_threshold_inclusive_at_boundary(self) -> None:
        c = _enc_citation("nail debridement")
        a = _assessment([c], [c], [c], [c])
        guard = ComplianceGuard(verifier=NLIStub(default=NLI_THRESHOLD))
        outcome = guard.verify(
            assessment=a,
            remediations=[],
            parsed=ParsedEncounter(),
            policy_text_index={},
        )
        assert outcome.verified

    def test_policy_citation_resolves_via_index(self) -> None:
        policy_text = "CMS NCCI Policy: a separately identifiable E/M service must be supported."
        c = _policy_citation(
            "cms-foo",
            span_text="a separately identifiable E/M service",
            rationale="A separate problem is required",
        )
        a = _assessment([c], [c], [c], [c])
        verifier = NLIStub(default=0.99)
        guard = ComplianceGuard(verifier=verifier)
        outcome = guard.verify(
            assessment=a,
            remediations=[],
            parsed=ParsedEncounter(),
            policy_text_index={"cms-foo": policy_text},
        )
        assert outcome.verified
        # The verifier should have been called with the resolved policy text
        # as premise, not the citation span text.
        premises = {pre for pre, _hyp in verifier.calls}
        assert policy_text in premises

    def test_unknown_policy_id_fails(self) -> None:
        c = _policy_citation("missing", "x", "claim")
        a = _assessment([c], [_enc_citation("y")], [_enc_citation("y")], [_enc_citation("y")])
        guard = ComplianceGuard(verifier=NLIStub(default=0.99))
        outcome = guard.verify(
            assessment=a,
            remediations=[],
            parsed=ParsedEncounter(),
            policy_text_index={},
        )
        assert not outcome.verified
        assert outcome.failures[0].location == "criterion=distinct_cc"

    def test_remediation_citations_are_verified(self) -> None:
        c_ok = _enc_citation("CC text")
        good_assessment = _assessment([c_ok], [c_ok], [c_ok], [c_ok])
        bad_remediation = RemediationSuggestion(
            criterion="independent_mdm",
            suggested_addition="Add an independent decision...",
            motivation=[
                _policy_citation(
                    "policy-x",
                    "policy span",
                    "rationale ignored by NLI",
                    entailed_paraphrase="paraphrase that NLI rejects",
                )
            ],
        )
        # NLI verifies entailed_paraphrase against the resolved policy text;
        # the rationale is no longer the hypothesis (5a path).
        scores = {
            ("policy span passage", "paraphrase that NLI rejects"): 0.5,
        }
        # Build the index so the policy citation resolves.
        policy_index = {"policy-x": "policy span passage"}
        verifier = NLIStub(scores=scores, default=0.99)
        outcome = ComplianceGuard(verifier=verifier).verify(
            assessment=good_assessment,
            remediations=[bad_remediation],
            parsed=ParsedEncounter(),
            policy_text_index=policy_index,
        )
        assert not outcome.verified
        assert len(outcome.failures) == 1
        assert outcome.failures[0].location == "remediation=independent_mdm"

    def test_blocked_reasons_render_includes_score(self) -> None:
        f = VerificationFailure(
            location="criterion=independent_mdm",
            rationale="MDM addresses separate problem",
            cited_span="discussed risks of debridement",
            entailment_score=0.42,
        )
        rendered = f.render()
        assert "criterion=independent_mdm" in rendered
        assert "0.42" in rendered
        assert "0.75" in rendered
        assert "MDM addresses separate problem" in rendered

    def test_truncate_long_spans(self) -> None:
        long = "x" * 500
        out = _truncate(long, 100)
        assert out.endswith("...")
        assert len(out) == 100


class TestVerifyResponse:
    def test_passed_when_all_entailed(self) -> None:
        c = _enc_citation("nail debridement")
        a = _assessment([c], [c], [c], [c])
        resp = _response(a)
        verified = verify_response(
            response=resp,
            parsed=ParsedEncounter(),
            policy_text_index={},
            verifier=NLIStub(default=0.99),
        )
        assert verified.compliance_status == "PASSED"
        assert verified.assessment is not None
        assert verified.blocked_reasons is None

    def test_blocked_strips_assessment_and_remediations(self) -> None:
        c = _enc_citation("nail debridement", rationale="not entailed claim")
        a = _assessment([c], [c], [c], [c])
        resp = _response(a)
        resp = resp.model_copy(
            update={
                "remediations": [
                    RemediationSuggestion(
                        criterion="independent_mdm",
                        suggested_addition="x",
                        motivation=[
                            c.model_copy(update={"source_type": "policy", "policy_id": "p"})
                        ],
                    )
                ]
            }
        )
        verified = verify_response(
            response=resp,
            parsed=ParsedEncounter(),
            policy_text_index={"p": "policy text"},
            verifier=NLIStub(default=0.30),  # everything fails
        )
        assert verified.compliance_status == "BLOCKED"
        assert verified.assessment is None
        assert verified.remediations == []
        assert verified.blocked_reasons is not None
        assert len(verified.blocked_reasons) >= 1

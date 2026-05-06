"""Compliance Guard agent (EPIC-005).

Architecturally separate from the synthesis-side agents. Constitution
Principle II is non-negotiable: this module MUST NOT import from
``app.agents.parser``, ``app.agents.analyzer``, or ``app.agents.drafter``.
The reverse is also forbidden. Both directions are enforced by the
import-graph lint in ``scripts/check_imports.py`` (T138) running in CI.
"""

from app.agents.compliance_guard.agent import (
    NLI_THRESHOLD,
    ComplianceGuard,
    GuardOutcome,
    VerificationFailure,
    verify_response,
)
from app.agents.compliance_guard.nli import (
    NLIStub,
    NLIVerifier,
    build_default_verifier,
)

__all__ = [
    "NLI_THRESHOLD",
    "ComplianceGuard",
    "GuardOutcome",
    "NLIStub",
    "NLIVerifier",
    "VerificationFailure",
    "build_default_verifier",
    "verify_response",
]

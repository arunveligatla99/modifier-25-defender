"""Pydantic v2 data contracts for Modifier 25 Defender.

Every type that crosses an agent boundary or the API surface lives in this
package. ``dict[str, Any]`` is not allowed at module boundaries (Constitution
coding standard CS-1).

Modules:

- :mod:`app.schemas.text` shared primitive types (``TextSpan``, ``Citation``)
- :mod:`app.schemas.parser` Documentation Parser output (``ParsedEncounter``)
- :mod:`app.schemas.assessment` Defensibility Analyzer output
- :mod:`app.schemas.remediation` Remediation Drafter output
- :mod:`app.schemas.api` API request/response (``DefenderRequest``,
  ``DefenderResponse``)
- :mod:`app.schemas.corpus` indexed corpus chunks
"""

from app.schemas.api import DefenderRequest, DefenderResponse
from app.schemas.assessment import (
    CriteriaMap,
    CriterionScore,
    DefensibilityAssessment,
    Verdict,
)
from app.schemas.corpus import AuthorityTier, CorpusChunk
from app.schemas.parser import ParsedEncounter
from app.schemas.remediation import CriterionName, RemediationSuggestion
from app.schemas.text import Citation, SourceType, TextSpan

__all__ = [
    "AuthorityTier",
    "Citation",
    "CorpusChunk",
    "CriteriaMap",
    "CriterionName",
    "CriterionScore",
    "DefenderRequest",
    "DefenderResponse",
    "DefensibilityAssessment",
    "ParsedEncounter",
    "RemediationSuggestion",
    "SourceType",
    "TextSpan",
    "Verdict",
]

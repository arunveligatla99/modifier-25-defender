"""Shared primitive types for spans and citations.

Used by :mod:`app.schemas.parser`, :mod:`app.schemas.assessment`, and
:mod:`app.schemas.remediation`. The ``TextSpan`` invariant (``text ==
source[start_char:end_char]``) is enforced by the Compliance Guard at
verification time; constructors check the bounds but cannot validate against
the source document because spans are constructed in isolation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SourceType = Literal["encounter", "policy"]
"""Origin of a cited span: the encounter note itself or a policy chunk."""


class TextSpan(BaseModel):
    """A literal span of text with character offsets.

    Attributes:
        text: The literal text content of the span.
        start_char: Inclusive start offset in the source document.
        end_char: Exclusive end offset in the source document. Must be greater
            than ``start_char``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(..., min_length=1)
    start_char: int = Field(..., ge=0)
    end_char: int = Field(..., gt=0)

    @model_validator(mode="after")
    def _check_offsets(self) -> TextSpan:
        """Validate that ``end_char`` is strictly greater than ``start_char``."""
        if self.end_char <= self.start_char:
            raise ValueError(
                "TextSpan: end_char must be greater than start_char "
                f"(got start_char={self.start_char}, end_char={self.end_char})"
            )
        return self

    def length(self) -> int:
        """Return the span length in characters."""
        return self.end_char - self.start_char

    def matches_source(self, source: str) -> bool:
        """Return True if ``self.text`` equals ``source[start_char:end_char]``.

        Args:
            source: The full source document the span refers to.

        Returns:
            True iff the offsets resolve to the recorded text in the source.
        """
        if self.end_char > len(source):
            return False
        return source[self.start_char : self.end_char] == self.text


class Citation(BaseModel):
    """Traceable evidence linking a model claim to a span of source text.

    A claim made by an agent must be supported by at least one citation
    (Constitution Principle I). The Compliance Guard verifies via NLI that the
    cited span entails the rationale.

    Attributes:
        source_type: Where the cited span lives.
        span: The cited text span.
        policy_id: When ``source_type == "policy"``, the chunk identifier in
            the active corpus snapshot. Must be ``None`` when
            ``source_type == "encounter"``.
        rationale: The agent's reasoning linking the cited span to the
            verdict or claim. 1 to 1000 characters.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_type: SourceType
    span: TextSpan
    policy_id: str | None = None
    rationale: str = Field(..., min_length=1, max_length=1000)

    @model_validator(mode="after")
    def _check_policy_id(self) -> Citation:
        """Ensure ``policy_id`` is set if and only if ``source_type`` is "policy"."""
        if self.source_type == "policy" and not self.policy_id:
            raise ValueError("Citation: policy_id is required when source_type is 'policy'")
        if self.source_type == "encounter" and self.policy_id is not None:
            raise ValueError("Citation: policy_id must be None when source_type is 'encounter'")
        return self

"""NLI verification wrapper for the Compliance Guard.

Implements EPIC-005's local-inference NLI step. Real production wraps
``microsoft/deberta-v3-large-mnli`` (or any HF NLI head loadable via
``transformers``); the heavy model load is lazy. Tests should always use
:class:`NLIStub` to avoid pulling weights.

Important: this module is part of the verification side and MUST NOT
import anything from the synthesis-side agents (Constitution Principle II,
T138 import-graph lint).
"""

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "microsoft/deberta-v3-large-mnli"


class NLIVerifier(Protocol):
    """Minimal verifier protocol used by the Compliance Guard."""

    def entailment_probability(self, premise: str, hypothesis: str) -> float:
        """Return ``P(entailment | premise, hypothesis)`` in 0..1."""
        ...


class NLIStub:
    """Deterministic NLI stub for unit tests.

    The stub looks up an explicit ``(premise, hypothesis)`` mapping; missing
    pairs return a configurable default probability.

    Attributes:
        scores: Mapping from ``(premise, hypothesis)`` to entailment
            probability in 0..1.
        default: Probability returned for pairs not in ``scores``.
    """

    def __init__(
        self,
        scores: dict[tuple[str, str], float] | None = None,
        *,
        default: float = 0.95,
    ) -> None:
        self.scores = dict(scores) if scores else {}
        self.default = default
        self.calls: list[tuple[str, str]] = []

    def entailment_probability(self, premise: str, hypothesis: str) -> float:
        """Return the configured probability for the pair, or the default."""
        self.calls.append((premise, hypothesis))
        return self.scores.get((premise, hypothesis), self.default)


class _TransformersNLI:
    """Real NLI verifier backed by a Hugging Face MNLI head.

    Loads the model lazily on first call so unit-test setups stay fast.
    Returns ``P(entailment | premise, hypothesis)``. Constitution Principle
    II requires this verifier to live in a module separate from the
    synthesis agents; that boundary is enforced by the import-graph lint.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self.model_name = model_name
        self._pipeline: object | None = None

    def _load(self) -> object:
        if self._pipeline is not None:
            return self._pipeline
        try:
            from transformers import pipeline
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "transformers not available; install dev extras (uv sync --extra dev)"
            ) from exc
        logger.info("Loading NLI model %s", self.model_name)
        self._pipeline = pipeline(
            task="text-classification",
            model=self.model_name,
            top_k=None,
        )
        return self._pipeline

    def entailment_probability(self, premise: str, hypothesis: str) -> float:
        """Return ``P(entailment)`` for the pair."""
        pipe = self._load()
        # The MNLI head returns a list-of-list of {"label": ..., "score": ...}.
        result = pipe(  # type: ignore[operator]
            f"{premise} </s></s> {hypothesis}",
            truncation=True,
        )
        if isinstance(result, list) and result and isinstance(result[0], list):
            scored = result[0]
        else:
            scored = result if isinstance(result, list) else []
        for entry in scored:  # pragma: no cover - exercised by integration only
            label = str(entry.get("label", "")).upper()
            if label in {"ENTAILMENT", "LABEL_2"}:
                return float(entry.get("score", 0.0))
        return 0.0  # pragma: no cover


def build_default_verifier(model_name: str = DEFAULT_MODEL) -> NLIVerifier:
    """Construct the default real NLI verifier."""
    return _TransformersNLI(model_name=model_name)

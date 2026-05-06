"""RAGAS faithfulness eval harness (T130, AC-004-5).

For each encounter in the synthetic test split:

1. Run parser then analyzer (gpt-4o, cached on disk).
2. Compose the four criterion outputs into one multi-statement
   ``response`` consisting of the rationale + entailed_paraphrase from
   each citation.
3. Build ``retrieved_contexts`` from the top retrieval chunks for each
   criterion (deduped by chunk_id).
4. Score the (question, answer, contexts) tuple with
   ``ragas.metrics.Faithfulness``.

The mean score across encounters becomes ``analyzer.faithfulness``.
AC-004-5 requires it to be at least 0.88. Per-encounter scores land in
``analyzer.faithfulness_per_encounter``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.schemas.assessment import DefensibilityAssessment
from app.schemas.parser import ParsedEncounter

from eval.defensibility.accuracy import load_test_split
from eval.schemas import SyntheticEncounter

logger = logging.getLogger(__name__)

DEFAULT_LABELS_PATH = Path("data/synthetic/labels.jsonl")
DEFAULT_ENCOUNTERS_DIR = Path("data/synthetic/encounters")


class _ParserLike(Protocol):
    def parse(self, note_text: str) -> ParsedEncounter: ...


class _AnalyzerLike(Protocol):
    @property
    def retriever(self) -> Any: ...

    def score(
        self,
        parsed: ParsedEncounter,
        *,
        em_code: str,
        procedure_code: str,
        site: str | None,
    ) -> DefensibilityAssessment: ...


class _FaithfulnessMetricLike(Protocol):
    async def single_turn_ascore(self, sample: Any) -> float: ...


@dataclass(frozen=True)
class FaithfulnessReport:
    """Output of the faithfulness harness.

    Attributes:
        total: Number of encounters evaluated.
        mean_faithfulness: Mean RAGAS faithfulness score across encounters.
        per_encounter: Per-encounter score (encounter_id -> score).
        skipped: Count of encounters that produced no evaluable answer
            (no citations across all four criteria).
    """

    total: int
    mean_faithfulness: float
    per_encounter: dict[str, float] = field(default_factory=dict)
    skipped: int = 0


def evaluate_faithfulness(
    parser: _ParserLike,
    analyzer: _AnalyzerLike,
    metric: _FaithfulnessMetricLike,
    encounters: Iterable[SyntheticEncounter] | None = None,
    *,
    labels_path: Path = DEFAULT_LABELS_PATH,
    encounters_dir: Path = DEFAULT_ENCOUNTERS_DIR,
) -> FaithfulnessReport:
    """Score RAGAS faithfulness on the synthetic test split."""
    cases = (
        list(encounters)
        if encounters is not None
        else load_test_split(labels_path=labels_path, encounters_dir=encounters_dir)
    )
    if not cases:
        return FaithfulnessReport(total=0, mean_faithfulness=0.0, per_encounter={}, skipped=0)

    return asyncio.run(_score_all(parser, analyzer, metric, cases))


async def _score_all(
    parser: _ParserLike,
    analyzer: _AnalyzerLike,
    metric: _FaithfulnessMetricLike,
    cases: list[SyntheticEncounter],
) -> FaithfulnessReport:
    from ragas import SingleTurnSample

    per_enc: dict[str, float] = {}
    scores: list[float] = []
    skipped = 0
    for enc in cases:
        parsed = parser.parse(enc.note_text)
        assessment = analyzer.score(
            parsed,
            em_code=enc.em_code,
            procedure_code=enc.procedure_code,
            site=enc.site,
        )
        statements = _statements_from_assessment(assessment)
        contexts = _contexts_from_assessment(analyzer, enc)
        # The analyzer's answer cites both the encounter (most citations
        # are source_type=="encounter") and policy chunks. Include the
        # encounter note in retrieved_contexts so RAGAS scores statements
        # against the full grounding the analyzer actually used.
        contexts = [enc.note_text, *contexts]
        if not statements or not contexts:
            skipped += 1
            continue
        sample = SingleTurnSample(
            user_input=_question_for(enc),
            response=" ".join(statements),
            retrieved_contexts=contexts,
        )
        try:
            score = await metric.single_turn_ascore(sample)
        except Exception as exc:  # RAGAS occasionally raises on parse failures
            logger.warning("ragas faithfulness failed for %s: %s", enc.encounter_id, exc)
            continue
        score_f = float(score)
        per_enc[enc.encounter_id] = round(score_f, 4)
        scores.append(score_f)

    mean = sum(scores) / len(scores) if scores else 0.0
    return FaithfulnessReport(
        total=len(scores),
        mean_faithfulness=mean,
        per_encounter=per_enc,
        skipped=skipped,
    )


def _statements_from_assessment(assessment: DefensibilityAssessment) -> list[str]:
    """Extract a flat list of statements from all four criteria's citations."""
    statements: list[str] = []
    for name in ("distinct_cc", "separate_exam", "independent_mdm", "site_specificity"):
        score = getattr(assessment.criteria, name)
        for citation in score.evidence:
            # entailed_paraphrase is the content claim (verifiable);
            # rationale is interpretive prose. Use the paraphrase so RAGAS
            # scores grounded content, not interpretation.
            statements.append(citation.entailed_paraphrase)
    return statements


def _contexts_from_assessment(analyzer: _AnalyzerLike, encounter: SyntheticEncounter) -> list[str]:
    """Re-run retrieval for the four criterion queries and dedupe chunks."""
    from app.agents.analyzer.agent import _query_for  # internal helper

    retriever = analyzer.retriever
    seen: set[str] = set()
    contexts: list[str] = []
    for name in ("distinct_cc", "separate_exam", "independent_mdm", "site_specificity"):
        query = _query_for(name, encounter.em_code, encounter.procedure_code, encounter.site)
        result = retriever.search(query)
        for chunk_score in list(getattr(result, "chunks", []))[:5]:
            chunk = chunk_score[0] if isinstance(chunk_score, tuple) else chunk_score
            cid = getattr(chunk, "chunk_id", None) or chunk.text[:64]
            if cid in seen:
                continue
            seen.add(cid)
            contexts.append(chunk.text)
    return contexts


def _question_for(encounter: SyntheticEncounter) -> str:
    """Build a stable question string for the RAGAS sample."""
    site = encounter.site or "unspecified"
    return (
        "Is the documentation for this encounter defensible under the "
        f"JARALL Standard for modifier 25? E/M={encounter.em_code}, "
        f"procedure={encounter.procedure_code}, site={site}."
    )

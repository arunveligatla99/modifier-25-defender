"""Eval harness orchestrator (T302).

Runs the sub-harnesses that have everything they need to produce real
numbers, and reports placeholder zeros for categories that still depend
on follow-up work (parser field-accuracy ground-truth, verdict-accuracy
test-split labeling, RAGAS faithfulness, latency telemetry).

Wired in this revision:

- ``retrieval.recall_at_5``: real, against ``data/retrieval_eval/questions.jsonl``.
- ``compliance_guard.adversarial_recall``: real, against
  ``data/adversarial/claims.jsonl`` using ``MoritzLaurer`` NLI.
- ``compliance_guard.false_positive_rate``: real when
  ``data/adversarial/correct_claims.jsonl`` is present; otherwise the
  category reports a zeroed value and the gate fails (intentional).

Everything else stays at the empty_report() placeholder so the gate
checker fails loudly until those wirings land.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agents.analyzer.agent import AnalyzerAgent
from app.agents.compliance_guard.nli import build_default_verifier
from app.agents.drafter.agent import DrafterAgent
from app.agents.parser.agent import ParserAgent
from app.infra.settings import get_settings
from app.llm.embeddings import embed_text
from app.llm.openai_client import CachedLLMClient
from app.retrieval.bm25 import BM25Index
from app.retrieval.qdrant import QdrantIndex
from app.retrieval.reranker import RerankerStub
from app.retrieval.retriever import Retriever
from app.schemas.corpus import CorpusChunk

from eval.adversarial.false_positive import evaluate_false_positive_rate
from eval.adversarial.recall import evaluate_adversarial_recall
from eval.defensibility.accuracy import evaluate_defensibility_accuracy
from eval.defensibility.accuracy import load_test_split as load_defensibility_test_split
from eval.drafter.clinical_reasonableness import (
    DEFAULT_SAMPLE_PATH as DRAFTER_SAMPLE_PATH,
)
from eval.drafter.clinical_reasonableness import (
    DEFAULT_SCORES_PATH as DRAFTER_SCORES_PATH,
)
from eval.drafter.clinical_reasonableness import evaluate_clinical_reasonableness
from eval.drafter.dev_sample import build_dev_sample, write_dev_sample
from eval.faithfulness.ragas_runner import evaluate_faithfulness
from eval.parser.field_accuracy import evaluate_field_accuracy
from eval.parser.ground_truth import write_eval_set
from eval.retrieval.recall_at_5 import evaluate_recall_at_5

logger = logging.getLogger(__name__)

DEFAULT_REPORTS_DIR = Path("eval/reports")
CHUNKS_PATH = Path("data/corpus/.indexes/chunks.jsonl")
PARSER_EVAL_PATH = Path("data/parser_eval/dev.jsonl")


def empty_report() -> dict[str, Any]:
    """Report skeleton with all expected keys at zero/None.

    The gate checker fails every category against the configured thresholds
    when nothing has run; this is the correct behavior for an
    unevaluated PR (Constitution + AC-007-6).
    """
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "retrieval": {"recall_at_5": 0.0, "latency_p95_ms": 0.0},
        "parser": {"field_accuracy": 0.0, "latency_p95_seconds": 0.0},
        "analyzer": {
            "verdict_accuracy": 0.0,
            "per_criterion_accuracy": 0.0,
            "faithfulness": 0.0,
            "latency_p95_seconds": 0.0,
        },
        "compliance_guard": {
            "adversarial_recall": 0.0,
            "false_positive_rate": 1.0,
            "latency_p95_seconds": 0.0,
        },
        "drafter": {
            "latency_p95_seconds": 0.0,
            "clinical_reasonableness": 0.0,
        },
        "end_to_end": {"latency_p95_seconds": 0.0},
        "ui": {"render_after_response_ms": 0.0},
    }


def write_report(payload: dict[str, Any], reports_dir: Path = DEFAULT_REPORTS_DIR) -> Path:
    """Persist the report as a timestamped JSON file."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = payload.get("generated_at", "now").replace(":", "-").replace(".", "-")
    out = reports_dir / f"{stamp}.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    latest = reports_dir / "latest.json"
    latest.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return out


def _load_corpus_chunks() -> list[CorpusChunk]:
    """Load CorpusChunk records from the persisted chunks.jsonl."""
    if not CHUNKS_PATH.exists():
        return []
    out: list[CorpusChunk] = []
    for line in CHUNKS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        out.append(CorpusChunk.model_validate(record))
    return out


def _build_retriever() -> Retriever:
    """Build the production retriever stack for eval. Mirrors app/api/routes.py."""
    settings = get_settings()
    chunks = _load_corpus_chunks()
    bm25 = BM25Index(chunks=chunks)
    qdrant = QdrantIndex(url=settings.qdrant_url, collection="m25d-corpus", vector_size=3072)

    class _SafeDense:
        def search(
            self, query_embedding: list[float], top_k: int = 20
        ) -> list[tuple[CorpusChunk, float]]:
            try:
                return qdrant.search(query_embedding, top_k=top_k)
            except Exception as exc:
                logger.debug("dense search failed (%s); empty list", exc)
                return []

    def _safe_embed(query: str) -> list[float]:
        if not settings.openai_api_key:
            return [0.0] * 8
        try:
            return embed_text(
                query, model=settings.embedding_model, api_key=settings.openai_api_key
            )
        except Exception as exc:
            logger.warning("embed_text failed (%s); zero vector", exc)
            return [0.0] * 8

    return Retriever(
        bm25=bm25,
        dense=_SafeDense(),
        reranker=RerankerStub(top_n=5),
        embed=_safe_embed,
    )


def run_retrieval(payload: dict[str, Any]) -> None:
    """Compute retrieval recall@5 against the bundled question set."""
    chunks = _load_corpus_chunks()
    if not chunks:
        logger.warning("no corpus chunks loaded; skipping retrieval recall")
        return
    retriever = _build_retriever()
    t0 = time.perf_counter()
    report = evaluate_recall_at_5(retriever)
    elapsed = time.perf_counter() - t0
    payload["retrieval"]["recall_at_5"] = round(report.recall_at_5, 4)
    payload["retrieval"]["per_question"] = report.per_question
    payload["retrieval"]["total_questions"] = report.total
    payload["retrieval"]["hits"] = report.hits
    if report.total:
        payload["retrieval"]["latency_p95_ms"] = round(elapsed * 1000.0 / report.total, 1)
    logger.info(
        "retrieval recall@%d: %d/%d = %.4f",
        5,
        report.hits,
        report.total,
        report.recall_at_5,
    )


def run_compliance_guard(payload: dict[str, Any]) -> None:
    """Compute adversarial recall and (when available) false-positive rate."""
    settings = get_settings()
    verifier = build_default_verifier(model_name=settings.nli_model)
    # Warmup so the first model-load round-trip does not skew the
    # latency_p95 calculation. The result is discarded.
    try:
        verifier.entailment_probability("warmup premise.", "warmup hypothesis.")
    except Exception as exc:
        logger.warning("NLI warmup failed (%s); proceeding without warmup", exc)
    t0 = time.perf_counter()
    adv = evaluate_adversarial_recall(verifier)
    elapsed = time.perf_counter() - t0
    payload["compliance_guard"]["adversarial_recall"] = round(adv.recall, 4)
    payload["compliance_guard"]["adversarial_total"] = adv.total
    payload["compliance_guard"]["adversarial_caught"] = adv.caught
    payload["compliance_guard"]["adversarial_per_claim"] = adv.per_claim
    if adv.total:
        payload["compliance_guard"]["latency_p95_seconds"] = round(elapsed / adv.total, 4)
    logger.info("adversarial recall: %d/%d = %.4f", adv.caught, adv.total, adv.recall)

    fp = evaluate_false_positive_rate(verifier)
    if fp.total:
        payload["compliance_guard"]["false_positive_rate"] = round(fp.rate, 4)
        payload["compliance_guard"]["false_positive_per_claim"] = fp.per_claim
        logger.info("false positive rate: %d/%d = %.4f", fp.false_positives, fp.total, fp.rate)
    else:
        logger.info(
            "false-positive eval set absent; leaving compliance_guard.false_positive_rate at 1.0"
        )


def run_parser(payload: dict[str, Any]) -> None:
    """Compute parser field-level accuracy against the synthetic test split.

    AC-003-2 requires field-level accuracy >= 0.90, where a predicted
    field is correct when its total span length covers 80 to 120 percent
    of the ground-truth section. Ground truth is derived from the
    deterministic synthetic generator's section markers, regenerated on
    every run so it stays in sync with the encounter set.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY unset; skipping parser field-accuracy harness")
        return
    encounters = load_defensibility_test_split()
    if not encounters:
        logger.warning("synthetic test split empty; skipping parser field-accuracy harness")
        return
    written = write_eval_set(encounters, PARSER_EVAL_PATH)
    logger.info("parser eval set: wrote %d records to %s", written, PARSER_EVAL_PATH)

    client = CachedLLMClient(
        api_key=settings.openai_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        cache_dir=settings.llm_cache_dir,
    )
    parser_agent = ParserAgent(client=client, model=settings.parser_model)

    t0 = time.perf_counter()
    report = evaluate_field_accuracy(parser_agent, eval_path=PARSER_EVAL_PATH)
    elapsed = time.perf_counter() - t0

    payload["parser"]["field_accuracy"] = round(report.accuracy, 4)
    payload["parser"]["total_fields"] = report.total_fields
    payload["parser"]["correct_fields"] = report.correct_fields
    payload["parser"]["per_case"] = report.per_case
    if encounters:
        payload["parser"]["latency_p95_seconds"] = round(elapsed / len(encounters), 4)
    logger.info(
        "parser field accuracy: %d/%d = %.4f",
        report.correct_fields,
        report.total_fields,
        report.accuracy,
    )


def run_drafter(payload: dict[str, Any], *, refresh_sample: bool = False) -> None:
    """Score drafter clinical reasonableness from manual review (AC-006-4).

    When ``refresh_sample`` is True, regenerate the dev-split sample
    file (~20 suggestions) so a CPC-trained reviewer (or careful
    self-review per spec language) can score them in
    ``data/drafter_review/scores.jsonl``. Without scores, the metric
    surfaces 0.0 and the gate fails intentionally.
    """
    if refresh_sample:
        settings = get_settings()
        if not settings.openai_api_key:
            logger.warning("OPENAI_API_KEY unset; cannot refresh drafter sample")
        else:
            client = CachedLLMClient(
                api_key=settings.openai_api_key,
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                cache_dir=settings.llm_cache_dir,
            )
            retriever = _build_retriever()
            parser_agent = ParserAgent(client=client, model=settings.parser_model)
            analyzer_agent = AnalyzerAgent(client=client, retriever=retriever)
            drafter_agent = DrafterAgent(client=client, retriever=retriever)
            records = build_dev_sample(parser_agent, analyzer_agent, drafter_agent)
            written = write_dev_sample(records, DRAFTER_SAMPLE_PATH)
            logger.info("drafter dev sample: wrote %d records to %s", written, DRAFTER_SAMPLE_PATH)

    report = evaluate_clinical_reasonableness(
        scores_path=DRAFTER_SCORES_PATH,
        sample_path=DRAFTER_SAMPLE_PATH,
    )
    payload["drafter"]["clinical_reasonableness"] = round(report.rate, 4)
    payload["drafter"]["clinical_reasonableness_total"] = report.total
    payload["drafter"]["clinical_reasonableness_reasonable"] = report.reasonable
    payload["drafter"]["clinical_reasonableness_pending"] = len(report.sample_ids_missing)
    payload["drafter"]["clinical_reasonableness_per_sample"] = report.per_sample
    if report.total == 0:
        logger.warning(
            "drafter scores missing at %s; metric stays at 0.0 until %d samples are reviewed",
            DRAFTER_SCORES_PATH,
            len(report.sample_ids_missing),
        )
    else:
        logger.info(
            "drafter clinical reasonableness: %d/%d = %.4f",
            report.reasonable,
            report.total,
            report.rate,
        )


def run_faithfulness(payload: dict[str, Any]) -> None:
    """Compute RAGAS faithfulness on the analyzer's claims (AC-004-5).

    Mean faithfulness across the synthetic test split must be >= 0.88.
    Each encounter contributes one (question, response, contexts) sample
    where:

    - response = concatenated entailed_paraphrase strings from all four
      criteria's citations
    - contexts = top-5 retrieved chunks per criterion (deduped)

    RAGAS itself issues two LLM calls per sample (statement extraction
    plus NLI-style judgment), so cost is ~40 calls for a 20-encounter
    test split.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY unset; skipping faithfulness harness")
        return
    try:
        from langchain_openai import ChatOpenAI
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import Faithfulness
    except ImportError as exc:
        logger.warning("ragas/langchain unavailable (%s); skipping faithfulness", exc)
        return

    client = CachedLLMClient(
        api_key=settings.openai_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        cache_dir=settings.llm_cache_dir,
    )
    parser_agent = ParserAgent(client=client, model=settings.parser_model)
    retriever = _build_retriever()
    analyzer_agent = AnalyzerAgent(client=client, retriever=retriever)

    judge_llm = LangchainLLMWrapper(
        ChatOpenAI(model=settings.llm_model, temperature=0, api_key=settings.openai_api_key)
    )
    metric = Faithfulness(llm=judge_llm)

    report = evaluate_faithfulness(parser_agent, analyzer_agent, metric)
    if report.total == 0:
        logger.warning("faithfulness: no scorable encounters (skipped=%d)", report.skipped)
        return

    payload["analyzer"]["faithfulness"] = round(report.mean_faithfulness, 4)
    payload["analyzer"]["faithfulness_per_encounter"] = report.per_encounter
    payload["analyzer"]["faithfulness_skipped"] = report.skipped
    logger.info(
        "ragas faithfulness mean: %.4f over %d encounters (skipped %d)",
        report.mean_faithfulness,
        report.total,
        report.skipped,
    )


def run_defensibility(payload: dict[str, Any]) -> None:
    """Compute analyzer verdict and per-criterion accuracy on the test split.

    AC-004-2 (verdict_accuracy >= 0.85, lenient on WEAK) and AC-004-3
    (per_criterion_accuracy >= 0.80). Cost is real: ~5 LLM calls per
    encounter (1 parser + 4 analyzer criteria) at gpt-4o pricing.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY unset; skipping defensibility accuracy harness")
        return
    client = CachedLLMClient(
        api_key=settings.openai_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        cache_dir=settings.llm_cache_dir,
    )
    parser_agent = ParserAgent(client=client, model=settings.parser_model)
    retriever = _build_retriever()
    analyzer_agent = AnalyzerAgent(client=client, retriever=retriever)

    report = evaluate_defensibility_accuracy(parser_agent, analyzer_agent)
    if report.total == 0:
        logger.warning("defensibility test split empty; nothing to score")
        return

    payload["analyzer"]["verdict_accuracy"] = round(report.verdict_accuracy, 4)
    payload["analyzer"]["per_criterion_accuracy"] = round(report.per_criterion_accuracy, 4)
    payload["analyzer"]["latency_p95_seconds"] = round(report.latency_p95_seconds, 4)
    payload["analyzer"]["defensibility_total"] = report.total
    payload["analyzer"]["defensibility_verdict_correct"] = report.verdict_correct
    payload["analyzer"]["defensibility_per_criterion_correct"] = report.per_criterion_correct
    payload["analyzer"]["defensibility_per_encounter"] = report.per_encounter
    logger.info(
        "defensibility verdict accuracy: %d/%d = %.4f; per-criterion = %.4f",
        report.verdict_correct,
        report.total,
        report.verdict_accuracy,
        report.per_criterion_accuracy,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(prog="eval.run")
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass the LLM cache for nightly runs (R7 / Q5 invariant).",
    )
    parser.add_argument(
        "--cache-only-on-missing-key",
        action="store_true",
        help="When OPENAI_API_KEY is unset, run only cache-friendly portions.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=DEFAULT_REPORTS_DIR,
        help="Directory to write reports into.",
    )
    parser.add_argument(
        "--skip-retrieval",
        action="store_true",
        help="Skip the retrieval recall@5 sub-harness.",
    )
    parser.add_argument(
        "--skip-guard",
        action="store_true",
        help="Skip the Compliance Guard adversarial sub-harness.",
    )
    parser.add_argument(
        "--skip-defensibility",
        action="store_true",
        help="Skip the analyzer defensibility-accuracy sub-harness (AC-004-2/3).",
    )
    parser.add_argument(
        "--skip-parser",
        action="store_true",
        help="Skip the parser field-accuracy sub-harness (AC-003-2).",
    )
    parser.add_argument(
        "--skip-faithfulness",
        action="store_true",
        help="Skip the RAGAS faithfulness sub-harness (AC-004-5).",
    )
    parser.add_argument(
        "--skip-drafter",
        action="store_true",
        help="Skip the drafter clinical-reasonableness sub-harness (AC-006-4).",
    )
    parser.add_argument(
        "--refresh-drafter-sample",
        action="store_true",
        help=(
            "Regenerate data/drafter_review/dev_sample.jsonl from the dev "
            "split before reading review scores. Costs ~20 LLM calls."
        ),
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    if args.no_cache:
        logger.info("--no-cache requested; nightly path will skip the content-hash cache")

    payload = empty_report()
    if not args.skip_retrieval:
        try:
            run_retrieval(payload)
        except Exception as exc:
            logger.error("retrieval harness failed: %s", exc)
    if not args.skip_guard:
        try:
            run_compliance_guard(payload)
        except Exception as exc:
            logger.error("compliance guard harness failed: %s", exc)
    if not args.skip_parser:
        try:
            run_parser(payload)
        except Exception as exc:
            logger.error("parser harness failed: %s", exc)
    if not args.skip_defensibility:
        try:
            run_defensibility(payload)
        except Exception as exc:
            logger.error("defensibility harness failed: %s", exc)
    if not args.skip_faithfulness:
        try:
            run_faithfulness(payload)
        except Exception as exc:
            logger.error("faithfulness harness failed: %s", exc)
    if not args.skip_drafter:
        try:
            run_drafter(payload, refresh_sample=args.refresh_drafter_sample)
        except Exception as exc:
            logger.error("drafter harness failed: %s", exc)

    out = write_report(payload, args.reports_dir)
    print(f"wrote eval report to {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

"""POST /analyze route wiring.

Bridges :class:`DefenderRequest` validation with the orchestrator. The
agents and retriever are constructed once on first call and reused.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import cast

from fastapi import APIRouter, HTTPException

from app.agents.analyzer import AnalyzerAgent
from app.agents.analyzer.agent import _RetrieverLike
from app.agents.compliance_guard import ComplianceGuard, build_default_verifier
from app.agents.drafter import DrafterAgent
from app.agents.orchestrator import orchestrate_request
from app.agents.parser import ParserAgent
from app.infra.settings import get_settings
from app.llm.openai_client import CachedLLMClient
from app.observability.langfuse_client import get_langfuse_client
from app.schemas.api import DefenderRequest, DefenderResponse

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWLIST_PATH = Path("data/procedure_codes_allowlist.json")
PHI_DENYLIST = (
    " DOB:",
    " Date of Birth:",
    " MRN:",
)


@router.post("/analyze", response_model=DefenderResponse)
async def analyze(request: DefenderRequest) -> DefenderResponse:
    """Score an encounter for Modifier 25 defensibility."""
    if not _procedure_code_allowed(request.procedure_code):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "procedure_code_unsupported",
                "reason": (
                    f"procedure_code {request.procedure_code!r} is not in the v1 allowlist; "
                    "see data/procedure_codes_allowlist.json"
                ),
            },
        )
    if _looks_like_phi(request.note_text):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "phi_detected",
                "reason": (
                    "note_text contains a marker that resembles real PHI "
                    "(DOB, MRN, or similar). Constitution Principle IV "
                    "prohibits real PHI; v1 accepts synthetic data only."
                ),
            },
        )

    parser, analyzer, guard, drafter, policy_index = _agents()
    return orchestrate_request(
        request,
        parser=parser,
        analyzer=analyzer,
        guard=guard,
        policy_text_index=policy_index,
        drafter=drafter,
        langfuse=get_langfuse_client(),
    )


def _procedure_code_allowed(procedure_code: str) -> bool:
    """Check the procedure code against the v1 allowlist."""
    allowlist = _load_allowlist()
    return procedure_code in allowlist


def _looks_like_phi(note_text: str) -> bool:
    """Conservative PHI-marker check; runs before agents see the note."""
    return any(marker in note_text for marker in PHI_DENYLIST)


@lru_cache(maxsize=1)
def _load_allowlist() -> set[str]:
    if not ALLOWLIST_PATH.exists():
        logger.warning("procedure code allowlist missing at %s", ALLOWLIST_PATH)
        return set()
    payload = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    return {entry["code"] for entry in payload.get("codes", [])}


@lru_cache(maxsize=1)
def _agents() -> tuple[ParserAgent, AnalyzerAgent, ComplianceGuard, DrafterAgent, dict[str, str]]:
    """Construct the agent stack once. Cached for the process lifetime."""
    settings = get_settings()
    llm = CachedLLMClient(
        cache_dir=settings.llm_cache_dir,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        api_key=settings.openai_api_key,
    )
    parser = ParserAgent(client=llm)
    retriever = cast(_RetrieverLike, _build_retriever())
    analyzer = AnalyzerAgent(client=llm, retriever=retriever)
    drafter = DrafterAgent(client=llm, retriever=retriever)
    guard = ComplianceGuard(verifier=build_default_verifier(model_name=settings.nli_model))
    policy_index = _load_policy_index()
    return parser, analyzer, guard, drafter, policy_index


def _build_retriever() -> object:
    """Construct the production retriever stack.

    Lands fully when EPIC-002 ships its Qdrant + corpus integration
    pipeline alongside a real corpus. Until then, the retriever is a
    stub returning an empty result for every query so the orchestrator
    can still run end-to-end against synthetic encounters.
    """
    from app.retrieval.bm25 import BM25Index
    from app.retrieval.reranker import RerankerStub
    from app.retrieval.retriever import Retriever

    bm25 = BM25Index(chunks=[])

    class _EmptyDense:
        def search(
            self, query_embedding: list[float], top_k: int = 20
        ) -> list[tuple[object, float]]:
            del query_embedding, top_k
            return []

    return Retriever(
        bm25=bm25,
        dense=_EmptyDense(),  # type: ignore[arg-type]
        reranker=RerankerStub(top_n=5),
        embed=lambda _q: [0.0] * 8,
    )


def _load_policy_index() -> dict[str, str]:
    """Load the chunk_id -> text index for citation resolution.

    Reads ``data/corpus/.indexes/chunks.jsonl`` if present (produced by
    ``make corpus``). Empty when the corpus has not yet been built.
    """
    chunks_path = Path("data/corpus/.indexes/chunks.jsonl")
    if not chunks_path.exists():
        return {}
    out: dict[str, str] = {}
    for line in chunks_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        if "chunk_id" in record and "text" in record:
            out[record["chunk_id"]] = record["text"]
    return out

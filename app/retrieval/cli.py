"""``make corpus`` entry point.

Builds the reference corpus from source documents under ``data/corpus/``,
chunks them, embeds them, indexes them in Qdrant, and persists a serialized
chunk list alongside for the BM25 path. The actual document set is curated
by hand (T109); this CLI is the build pipeline that consumes it.

This script is intentionally a thin orchestrator. The library code
(:mod:`app.retrieval.chunker`, etc.) carries the testable logic.

Idempotency: re-running ``make corpus`` recreates the Qdrant collection
from scratch (``QdrantIndex.reset()``), so chunk IDs and vector contents
land deterministically given the same source documents and embedder.
AC-002-6.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from app.infra.settings import get_settings
from app.llm.embeddings import embed_batch
from app.retrieval.chunker import ChunkerConfig, chunk_document
from app.retrieval.metadata import enrich_chunk
from app.retrieval.qdrant import QdrantIndex
from app.schemas.corpus import AuthorityTier, CorpusChunk

logger = logging.getLogger(__name__)

DEFAULT_CORPUS_ROOT = Path("data/corpus")
DEFAULT_INDEX_DIR = Path("data/corpus/.indexes")
DEFAULT_QDRANT_COLLECTION = "m25d-corpus"


def load_manifest(corpus_root: Path) -> list[dict[str, str]]:
    """Load the corpus manifest mapping source files to metadata.

    The manifest is a ``manifest.jsonl`` file under ``corpus_root`` with one
    JSON record per document containing ``path``, ``authority_tier``, and
    optional ``section_heading`` and ``publication_date`` fields.
    """
    manifest_path = corpus_root / "manifest.jsonl"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"corpus manifest not found at {manifest_path}; "
            "create one with at least 30 entries (AC-002-1)"
        )
    records: list[dict[str, str]] = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def build_chunks(corpus_root: Path) -> list[CorpusChunk]:
    """Chunk every document listed in the manifest."""
    manifest = load_manifest(corpus_root)
    cfg = ChunkerConfig()
    chunks: list[CorpusChunk] = []
    for record in manifest:
        path = corpus_root / record["path"]
        if not path.exists():
            logger.warning("manifest references missing file %s; skipping", path)
            continue
        text = path.read_text(encoding="utf-8")
        raw_chunks = chunk_document(text, cfg)
        tier: AuthorityTier = record.get("authority_tier", "OTHER")  # type: ignore[assignment]
        for raw in raw_chunks:
            chunks.append(
                enrich_chunk(
                    raw,
                    source_document=record.get("path", str(path)),
                    authority_tier=tier,
                    section_heading=record.get("section_heading"),
                )
            )
    return chunks


def write_chunks(chunks: list[CorpusChunk], index_dir: Path) -> Path:
    """Persist chunks as JSONL for fast reload by the BM25 + Qdrant indexers."""
    index_dir.mkdir(parents=True, exist_ok=True)
    out = index_dir / "chunks.jsonl"
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for chunk in chunks:
            fh.write(chunk.model_dump_json() + "\n")
    return out


def index_in_qdrant(
    chunks: list[CorpusChunk],
    *,
    qdrant_url: str,
    api_key: str,
    embedding_model: str,
    collection: str = DEFAULT_QDRANT_COLLECTION,
) -> None:
    """Embed chunks via OpenAI and upsert into Qdrant.

    Recreates the collection so the indexed contents match the current chunk
    set exactly. Idempotent for AC-002-6.

    Raises:
        RuntimeError: If embedding generation fails.
    """
    if not chunks:
        logger.warning("no chunks to index in Qdrant")
        return
    logger.info(
        "embedding %d chunk(s) via %s and pushing to %s collection %s",
        len(chunks),
        embedding_model,
        qdrant_url,
        collection,
    )
    vectors = embed_batch(
        [c.text for c in chunks],
        model=embedding_model,
        api_key=api_key,
    )
    if not vectors:
        raise RuntimeError("embed_batch returned no vectors")
    dim = len(vectors[0])
    index = QdrantIndex(url=qdrant_url, collection=collection, vector_size=dim)
    index.reset()
    index.index(chunks, vectors)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(prog="app.retrieval.cli")
    parser.add_argument(
        "command",
        choices=["build-corpus"],
        help="Subcommand. Currently only 'build-corpus' is supported.",
    )
    parser.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX_DIR)
    parser.add_argument(
        "--skip-qdrant",
        action="store_true",
        help="Skip the embed + Qdrant upsert step (BM25 path still functions).",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)

    if args.command != "build-corpus":  # pragma: no cover
        parser.error(f"unsupported command {args.command!r}")

    try:
        chunks = build_chunks(args.corpus_root)
    except FileNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    if not chunks:
        sys.stderr.write("no chunks produced; check the manifest and source files\n")
        return 3

    out = write_chunks(chunks, args.index_dir)
    print(f"wrote {len(chunks)} chunks to {out}")

    if args.skip_qdrant:
        print("skipped Qdrant indexing per --skip-qdrant")
        return 0

    settings = get_settings()
    if not settings.openai_api_key:
        sys.stderr.write(
            "OPENAI_API_KEY not set; skipping embed + Qdrant upsert. "
            "BM25 retrieval will still work, dense retrieval will be empty.\n"
        )
        return 0

    try:
        index_in_qdrant(
            chunks,
            qdrant_url=settings.qdrant_url,
            api_key=settings.openai_api_key,
            embedding_model=settings.embedding_model,
        )
        print(f"indexed {len(chunks)} chunks in Qdrant collection " f"{DEFAULT_QDRANT_COLLECTION}")
    except Exception as exc:
        sys.stderr.write(f"Qdrant indexing failed: {exc}\n")
        sys.stderr.write("BM25 retrieval will still work, dense retrieval will be empty.\n")
        return 4
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

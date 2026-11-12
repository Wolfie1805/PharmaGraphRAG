"""
Build and verify the full-corpus Qdrant dense meaning index over data/processed/chunks.parquet.

Supports checkpoint & resume, bounded memory usage via small batch size, progress logging,
and strict 1:1 verification against chunks.parquet.
"""

import argparse
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

# Ensure offline execution against cached local HuggingFace model
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from app.retrieval.config import RetrievalConfig  # noqa: E402
from app.retrieval.meaning_search import MeaningSearchIndex  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build or verify full-corpus Qdrant dense meaning index."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/qdrant_db_full"),
        help="Target directory for Qdrant vector index (default: data/processed/qdrant_db_full).",
    )
    parser.add_argument(
        "--source-types",
        type=str,
        default=None,
        help=(
            "Comma-separated list of source_types to build or verify "
            "(e.g. annotation,drug_label,guideline or pubmed)."
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="Embedding batch size (small value keeps peak RAM well under 2 GB).",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=10,
        help="Write checkpoint and progress log every N batches.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Discard any previous checkpoint/collection in --output-dir and rebuild from scratch.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing Qdrant index against chunks.parquet without building.",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip post-build verification against chunks.parquet.",
    )
    args = parser.parse_args()

    cfg = RetrievalConfig()
    if args.force and args.output_dir.resolve() == cfg.qdrant_path.resolve():
        print(
            f"ERROR: Refusing --force on protected active index directory {cfg.qdrant_path}. "
            "Use --output-dir data/processed/qdrant_db_full.",
            flush=True,
        )
        return 1

    parsed_source_types = None
    if args.source_types is not None:
        parsed_source_types = [s.strip() for s in args.source_types.split(",") if s.strip()]
        if not parsed_source_types:
            print("ERROR: --source-types provided but no valid types specified.", flush=True)
            return 1

    index = MeaningSearchIndex(
        model_name=cfg.embedding_model,
        qdrant_path=args.output_dir,
        collection_name=cfg.collection_name,
        chunks_path=cfg.resolved_chunks_path,
    )

    try:
        if not args.verify_only:
            count = index.build_index(
                force_rebuild=args.force,
                batch_size=args.batch_size,
                checkpoint_every=args.checkpoint_every,
                source_types=parsed_source_types,
            )
            print(f"Indexed point count: {count}", flush=True)

        if not args.no_verify:
            report = index.verify_index(source_types=parsed_source_types)
            print("Index Verification Report:", flush=True)
            print(json.dumps(report, indent=2), flush=True)
            if not report["is_exact_match"]:
                print("ERROR: Qdrant index does not match chunks.parquet!", flush=True)
                return 1
    finally:
        index.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

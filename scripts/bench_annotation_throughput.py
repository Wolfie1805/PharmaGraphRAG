r"""
Measure uncontended dense-embedding throughput on a stratified 80-chunk sample of
source_type = 'annotation' from chunks.parquet / chunks_v2.parquet.

Intended to be run standalone with nothing else competing for CPU/RAM:
    $env:HF_HUB_OFFLINE="1"; $env:TRANSFORMERS_OFFLINE="1"
    .\.venv\Scripts\python.exe scripts/bench_annotation_throughput.py
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import duckdb  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

from app.retrieval.config import RetrievalConfig  # noqa: E402
from app.retrieval.meaning_search import get_process_ram_mb  # noqa: E402


def _stratified_sample(
    rows: List[Tuple[str, str, str, int]],
    sample_size: int = 80,
) -> List[Tuple[str, str, str, int]]:
    """
    Pick `sample_size` rows evenly across length-sorted indices (including short, median, and long).
    `rows` must already be sorted by text length ascending, chunk_id ascending.
    """
    n = len(rows)
    if n <= sample_size:
        return rows
    step = (n - 1) / float(sample_size - 1)
    indices = [int(round(i * step)) for i in range(sample_size)]
    return [rows[idx] for idx in indices]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Uncontended throughput benchmark for annotation stage (stratified 80 chunks)."
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=80,
        help="Number of stratified annotation chunks to encode (default: 80).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="Encoding batch size matching build_meaning_index.py (default: 16).",
    )
    parser.add_argument(
        "--chunks-path",
        type=Path,
        default=None,
        help="Optional chunks Parquet path (default: RetrievalConfig().resolved_chunks_path).",
    )
    args = parser.parse_args()

    cfg = (
        RetrievalConfig(chunks_path=args.chunks_path)
        if args.chunks_path is not None
        else RetrievalConfig()
    )
    chunks_path = cfg.resolved_chunks_path
    if not chunks_path.exists():
        print(f"ERROR: Chunks file not found at {chunks_path}", flush=True)
        return 1

    con = duckdb.connect(":memory:")
    rows = con.execute(
        f"""
        SELECT
            chunk_id,
            COALESCE(title, ''),
            COALESCE(content, ''),
            LENGTH(TRIM(COALESCE(title, '') || ' ' || COALESCE(content, ''))) AS char_len
        FROM '{chunks_path.as_posix()}'
        WHERE source_type = 'annotation'
        ORDER BY char_len ASC, chunk_id ASC
        """
    ).fetchall()

    total_annotations = len(rows)
    if total_annotations == 0:
        print("ERROR: Zero annotation chunks found.", flush=True)
        return 1

    sample = _stratified_sample(rows, sample_size=args.sample_size)
    texts = [
        (f"{title}. {content}".strip() if title else content.strip())
        for _, title, content, _ in sample
    ]
    sample_lens = [char_len for _, _, _, char_len in sample]

    model = SentenceTransformer(cfg.embedding_model)
    max_seq_len = getattr(model, "max_seq_length", None)
    device = str(getattr(model, "device", "cpu"))

    # Warmup pass (excluded from timed rate)
    warmup_texts = texts[: min(4, len(texts))]
    if warmup_texts:
        model.encode(warmup_texts, batch_size=args.batch_size, normalize_embeddings=True)

    t0 = time.perf_counter()
    model.encode(
        texts,
        batch_size=args.batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    elapsed_sec = time.perf_counter() - t0
    curr_ram_mb, peak_ram_mb = get_process_ram_mb()

    chunks_per_sec = len(texts) / elapsed_sec if elapsed_sec > 0 else 0.0
    est_total_sec = total_annotations / chunks_per_sec if chunks_per_sec > 0 else 0.0
    est_total_min = est_total_sec / 60.0

    print("=" * 72)
    print("ANNOTATION STAGE UNCONTENDED THROUGHPUT BENCHMARK (ESTIMATE)")
    print("=" * 72)
    print(f"Chunks table        : {chunks_path.as_posix()}")
    print(f"Embedding model     : {cfg.embedding_model}")
    print(f"Max sequence length : {max_seq_len}")
    print(f"Device              : {device}")
    print(f"Batch size          : {args.batch_size}")
    print(f"Total annotation    : {total_annotations}")
    print(
        f"Stratified sample   : {len(sample)} chunks "
        f"(char_len min={min(sample_lens)}, median={sample_lens[len(sample_lens)//2]}, "
        f"max={max(sample_lens)})"
    )
    print(f"Measured encode time: {elapsed_sec:.3f} s")
    print(f"Throughput          : {chunks_per_sec:.3f} chunks/s")
    print(f"Process RAM         : current={curr_ram_mb:.1f} MB | peak={peak_ram_mb:.1f} MB")
    print(
        f"Estimated stage time: {est_total_sec:.1f} s "
        f"({est_total_min:.1f} min / {est_total_min / 60.0:.2f} hr) [ESTIMATE]"
    )
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())


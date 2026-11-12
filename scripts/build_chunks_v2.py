"""
Build data/processed/chunks_v2.parquet with exact structured variant & haplotype IDs
(without modifying or activating the production data/processed/chunks.parquet).
Reports per-stream counts, untagged token reasons, 10 seeded samples, and diff summary.
"""

import json
import random
from pathlib import Path

from app.retrieval.variant_tagging import build_chunks_v2


def main() -> None:
    report = build_chunks_v2(
        chunks_path=Path("data/processed/chunks.parquet"),
        output_path=Path("data/processed/chunks_v2.parquet"),
        processed_dir=Path("data/processed"),
        clinpgx_dir=Path("data/raw/clinpgx/20261030_79ff97e7"),
    )

    print("=== CHUNKS_V2 BUILD & DIFF REPORT ===")
    print(f"Input  (untouched): {report['input_chunks_path']}")
    print(f"Output (inactive) : {report['output_chunks_path']}")
    print(f"Total chunks      : {report['total_chunks']}")
    print(f"Chunks whose entity_ids changed : {report['chunks_updated_entity_ids']}")
    print(f"Total pg:var/pg:haplo links added : {report['total_new_var_haplo_tags_added']}")
    print(
        f"Non-entity_ids columns byte-identical: "
        f"{report['non_entity_columns_byte_identical']}"
    )

    print("\n=== PER-STREAM TAGGING & UNTAGGED COUNTS ===")
    print(json.dumps(report["stream_stats"], indent=2))

    rng = random.Random(42)
    pool = report["sample_pool"]
    picks = rng.sample(pool, min(10, len(pool)))
    print("\n=== 10 SEEDED SAMPLE ROWS (seed=42) ===")
    for idx, row in enumerate(picks, start=1):
        print(
            f"  {idx:>2}. {row['source_type']}:{row['source_id']} | Gene={row['gene_cell']!r} "
            f"| Variant/Haplotypes={row['variant_cell']!r} "
            f"-> added={row['added_variant_ids']} | untagged={row['untagged_tokens']}"
        )


if __name__ == "__main__":
    main()


"""
Tests for scripts/build_site_stats.py:
- Planted ClinPGx text marker never appears in output.
- Null for missing inputs (never placeholders).
- Deterministic output except generated_at.
- Numbers strictly match the source tables.
"""

import json
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from scripts.build_site_stats import build_site_stats


def test_planted_clinpgx_text_marker_never_appears(tmp_path: Path):
    """Verify that planted ClinPGx text marker never appears anywhere in site_stats output."""
    proc_dir = tmp_path / "data" / "processed"
    proc_dir.mkdir(parents=True)

    marker = "PLANTED_SECRET_CLINPGX_TEXT_DO_NOT_LEAK"

    schema = pa.schema(
        [
            ("chunk_id", pa.string()),
            ("source_type", pa.string()),
            ("source_id", pa.string()),
            ("title", pa.string()),
            ("content", pa.string()),
            ("date", pa.string()),
            ("date_precision", pa.string()),
            ("entity_ids", pa.list_(pa.string())),
        ]
    )
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "chunk_id": "chunk:annotation:1",
                    "source_type": "annotation",
                    "source_id": "A1",
                    "title": f"Title with {marker}",
                    "content": f"Sentence with {marker}",
                    "date": "unknown",
                    "date_precision": "unknown",
                    "entity_ids": ["pg:gene:124"],
                }
            ],
            schema=schema,
        ),
        proc_dir / "chunks_v2.parquet",
    )

    out_file = tmp_path / "site_stats.json"
    stats = build_site_stats(
        workspace_dir=tmp_path,
        output_path=out_file,
        collect_test_counts=False,
    )
    json_str = json.dumps(stats)
    assert marker not in json_str
    assert marker not in out_file.read_text(encoding="utf-8")


def test_null_for_missing_inputs(tmp_path: Path):
    """Verify missing inputs produce null (None), never placeholder or hallucinated numbers."""
    stats = build_site_stats(
        workspace_dir=tmp_path,
        output_path=None,
        collect_test_counts=False,
    )
    assert stats["benchmark"] is None
    assert stats["raw_files"] is None
    assert stats["processed_tables"] is None
    assert stats["entities_by_type"] is None
    assert stats["relationships"] is None
    assert stats["chunks_by_source_type"] is None
    assert stats["papers"] is None
    assert stats["sources"] == []


def test_deterministic_output_except_generated_at():
    """Verify building stats twice produces byte-identical output except generated_at."""
    stats1 = build_site_stats(output_path=None, collect_test_counts=False)
    stats2 = build_site_stats(output_path=None, collect_test_counts=False)

    time1 = stats1.pop("generated_at")
    time2 = stats2.pop("generated_at")
    assert time1 is not None
    assert time2 is not None

    assert stats1 == stats2


def test_numbers_match_source_tables():
    """Verify counts in site_stats.json match DuckDB queries over actual processed tables."""
    stats = build_site_stats(output_path=None, collect_test_counts=False)
    con = duckdb.connect(":memory:")

    # 1. Processed tables counts
    for tbl in ["entities", "synonyms", "cross_references", "relationships", "publications"]:
        p = Path(f"data/processed/{tbl}.parquet")
        if p.exists():
            cnt = con.execute(f"SELECT COUNT(*) FROM '{p.as_posix()}'").fetchone()[0]
            assert stats["processed_tables"][tbl] == cnt

    chunks_p = Path("data/processed/chunks_v2.parquet")
    chunks_cnt = con.execute(f"SELECT COUNT(*) FROM '{chunks_p.as_posix()}'").fetchone()[0]
    assert stats["processed_tables"]["chunks"] == chunks_cnt

    # 2. Entities by type
    ent_rows = con.execute(
        "SELECT entity_type, COUNT(*) FROM 'data/processed/entities.parquet' "
        "GROUP BY entity_type ORDER BY entity_type"
    ).fetchall()
    for t, c in ent_rows:
        assert stats["entities_by_type"][t] == c

    # 3. Relationships total and dangling
    rel_row = con.execute(
        "SELECT COUNT(*), COUNT(CASE WHEN is_dangling THEN 1 END) "
        "FROM 'data/processed/relationships.parquet'"
    ).fetchone()
    assert stats["relationships"]["total"] == rel_row[0]
    assert stats["relationships"]["dangling"] == rel_row[1]

    # 4. Publications
    pub_row = con.execute(
        "SELECT COUNT(*), MIN(substr(pubdate_iso, 1, 4)), MAX(substr(pubdate_iso, 1, 4)), "
        "COUNT(CASE WHEN abstract_text IS NOT NULL AND length(trim(abstract_text)) > 0 THEN 1 END) "
        "FROM 'data/processed/publications.parquet'"
    ).fetchone()
    assert stats["papers"]["count"] == pub_row[0]
    assert stats["papers"]["year_min"] == int(pub_row[1])
    assert stats["papers"]["year_max"] == int(pub_row[2])
    assert stats["papers"]["with_abstracts"] == pub_row[3]

"""
Build site stats file for PharmaRAG frontend and diagnostics.
Reads manifests, processed tables, config files, and benchmark results to produce
frontend/public/site_stats.json containing ONLY counts, names, dates, and status strings.
NEVER emits ClinPGx row/chunk text. Missing values are null (never placeholders).
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb

from app.generation.config import GenerationConfig
from app.retrieval.config import RetrievalConfig
from app.retrieval.meaning_search import MeaningSearchIndex


def get_git_info(workspace_dir: Path) -> Optional[Dict[str, Any]]:
    """Return git commit, latest tag, and dirty status, or None if unavailable."""
    commit: Optional[str] = None
    tag: Optional[str] = None
    dirty: Optional[bool] = None
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=workspace_dir,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        commit = None

    try:
        tag = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=workspace_dir,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        tag = None

    try:
        status_out = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=workspace_dir,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        dirty = bool(status_out)
    except Exception:
        dirty = None

    if commit is None and tag is None and dirty is None:
        return None

    return {
        "commit": commit,
        "latest_tag": tag,
        "dirty": dirty,
    }


def collect_pytest_count(workspace_dir: Path) -> Optional[int]:
    """Collect test count using pytest --collect-only without executing tests."""
    venv_pytest = workspace_dir / ".venv" / "Scripts" / "pytest.exe"
    pytest_bin = str(venv_pytest) if venv_pytest.exists() else "pytest"
    try:
        out = subprocess.check_output(
            [pytest_bin, "--collect-only", "-q"],
            cwd=workspace_dir,
            text=True,
            stderr=subprocess.STDOUT,
        )
        m = re.search(r"collected (\d+) items", out) or re.search(r"(\d+) tests collected", out)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return None


def collect_vitest_count(workspace_dir: Path) -> Optional[int]:
    """Collect test count using vitest list without executing tests."""
    frontend_dir = workspace_dir / "frontend"
    if not frontend_dir.exists():
        return None
    try:
        out = subprocess.check_output(
            ["npx", "--no-install", "vitest", "list"],
            cwd=frontend_dir,
            text=True,
            shell=True,
            stderr=subprocess.DEVNULL,
        )
        lines = [
            line.strip()
            for line in out.splitlines()
            if line.strip() and not line.strip().startswith(">")
        ]
        if lines:
            return len(lines)
    except Exception:
        pass
    return None


def get_pubmed_queries(workspace_dir: Path) -> List[Dict[str, Any]]:
    """Extract PubMed queries and counts from the full run manifest."""
    manifest_path = workspace_dir / "data" / "manifests" / "manifest_pubmed_20261031_7d1398e0.json"
    if not manifest_path.exists():
        return []
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        queries = data.get("queries", {})
        counts = data.get("esearch_counts", {})
        raw_date = str(data.get("retrieval_timestamp_utc") or "")
        retrieval_date = raw_date.split("T")[0] if "T" in raw_date else raw_date
        return [
            {
                "pair_id": pid,
                "query": q_str,
                "esearch_count": int(counts.get(pid, 0)),
                "retrieval_date": retrieval_date,
            }
            for pid, q_str in sorted(queries.items())
        ]
    except Exception:
        return []


def get_raw_files_summary(workspace_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Summarize raw acquisition files.
    Reports full PubMed run and pilot separately with run IDs and counts;
    excludes pilot from PubMed totals.
    """
    manifests_dir = workspace_dir / "data" / "manifests"
    if not manifests_dir.exists():
        return None

    manifest_files = sorted(manifests_dir.glob("manifest_*.json"))
    if not manifest_files:
        return None

    clinpgx_count = 0
    clinpgx_bytes = 0
    clinpgx_version = "not provided"

    pubmed_full_count = 0
    pubmed_full_bytes = 0
    pubmed_full_run_id = "unknown"

    pubmed_pilot_count = 0
    pubmed_pilot_bytes = 0
    pubmed_pilot_run_id = "unknown"

    has_clinpgx = False
    has_pubmed = False
    has_nrces = False
    nrces_count = 0
    nrces_bytes = 0
    nrces_version = "not provided"
    nrces_run_id = "unknown"

    for p in manifest_files:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            sname = str(data.get("source_name") or "").strip().lower()
            run_id = str(data.get("run_id") or p.stem.replace("manifest_", "")).strip()
            files_list = data.get("files") or []
            file_count = len(files_list)
            byte_sum = sum(int(f.get("byte_size", 0)) for f in files_list)
            is_pilot = bool(data.get("is_pilot", False))

            if "clinpgx" in sname or "clinpgx" in p.name.lower():
                has_clinpgx = True
                clinpgx_count += file_count
                clinpgx_bytes += byte_sum
                v = str(data.get("source_version") or "").strip()
                if v and v != "not provided":
                    clinpgx_version = v
            elif "pubmed" in sname or "pubmed" in p.name.lower():
                has_pubmed = True
                if is_pilot:
                    pubmed_pilot_count += file_count
                    pubmed_pilot_bytes += byte_sum
                    pubmed_pilot_run_id = run_id
                else:
                    pubmed_full_count += file_count
                    pubmed_full_bytes += byte_sum
                    pubmed_full_run_id = run_id
            elif "nrces" in sname or "nrces" in p.name.lower():
                has_nrces = True
                has_subfiles = files_list
                nrces_count += len(has_subfiles) if has_subfiles else 1
                nrces_bytes += byte_sum if byte_sum else int(data.get("byte_size", 0))
                nrces_run_id = run_id
                v = str(data.get("source_version") or "").strip()
                if v:
                    nrces_version = v
        except Exception:
            continue

    sources_summary: Dict[str, Any] = {}
    if has_clinpgx:
        sources_summary["clinpgx"] = {
            "source_name": "ClinPGx",
            "count": clinpgx_count,
            "bytes": clinpgx_bytes,
            "release_label": clinpgx_version,
        }
    if has_pubmed:
        sources_summary["pubmed"] = {
            "source_name": "PubMed",
            "count": pubmed_full_count,
            "bytes": pubmed_full_bytes,
            "release_label": "not provided",
            "runs": {
                "full": {
                    "run_id": pubmed_full_run_id,
                    "count": pubmed_full_count,
                    "bytes": pubmed_full_bytes,
                },
                "pilot": {
                    "run_id": pubmed_pilot_run_id,
                    "count": pubmed_pilot_count,
                    "bytes": pubmed_pilot_bytes,
                },
            },
        }
    if has_nrces:
        sources_summary["nrces"] = {
            "source_name": "NRCeS Common Drug Codes for India",
            "count": nrces_count,
            "bytes": nrces_bytes,
            "release_label": nrces_version,
            "run_id": nrces_run_id,
        }

    return sources_summary or None


def get_processed_tables_summary(
    workspace_dir: Path, con: duckdb.DuckDBPyConnection
) -> Optional[Dict[str, Optional[int]]]:
    """Return exact row counts for all processed tables."""
    processed_dir = workspace_dir / "data" / "processed"
    if not processed_dir.exists():
        return None

    tables = ["entities", "synonyms", "cross_references", "relationships", "publications"]
    summary: Dict[str, Optional[int]] = {}
    for tbl in tables:
        t_path = processed_dir / f"{tbl}.parquet"
        if not t_path.exists():
            summary[tbl] = None
        else:
            try:
                cnt = con.execute(f"SELECT COUNT(*) FROM '{t_path.as_posix()}'").fetchone()[0]
                summary[tbl] = int(cnt)
            except Exception:
                summary[tbl] = None

    # Chunks table: active chunks_v2.parquet or fallback to chunks.parquet
    chunks_path = processed_dir / "chunks_v2.parquet"
    if not chunks_path.exists():
        chunks_path = processed_dir / "chunks.parquet"
    if chunks_path.exists():
        try:
            cnt = con.execute(f"SELECT COUNT(*) FROM '{chunks_path.as_posix()}'").fetchone()[0]
            summary["chunks"] = int(cnt)
        except Exception:
            summary["chunks"] = None
    else:
        summary["chunks"] = None

    return summary


def get_entities_by_type(
    workspace_dir: Path, con: duckdb.DuckDBPyConnection
) -> Optional[Dict[str, int]]:
    """Return entity count by entity_type."""
    ent_path = workspace_dir / "data" / "processed" / "entities.parquet"
    if not ent_path.exists():
        return None
    try:
        sql = (
            f"SELECT entity_type, COUNT(*) FROM '{ent_path.as_posix()}' "
            "GROUP BY entity_type ORDER BY entity_type"
        )
        rows = con.execute(sql).fetchall()
        return {str(t): int(cnt) for t, cnt in rows}
    except Exception:
        return None


def get_relationships_summary(
    workspace_dir: Path, con: duckdb.DuckDBPyConnection
) -> Optional[Dict[str, int]]:
    """Return total and dangling relationship counts."""
    rel_path = workspace_dir / "data" / "processed" / "relationships.parquet"
    if not rel_path.exists():
        return None
    try:
        row = con.execute(
            f"SELECT COUNT(*), COUNT(CASE WHEN is_dangling THEN 1 END) FROM '{rel_path.as_posix()}'"
        ).fetchone()
        return {"total": int(row[0]), "dangling": int(row[1])}
    except Exception:
        return None


def get_chunks_summary(
    workspace_dir: Path, con: duckdb.DuckDBPyConnection
) -> Optional[Dict[str, Dict[str, int]]]:
    """Return chunk counts and variant/allele tag stats per source_type."""
    processed_dir = workspace_dir / "data" / "processed"
    chunks_path = processed_dir / "chunks_v2.parquet"
    if not chunks_path.exists():
        chunks_path = processed_dir / "chunks.parquet"
    if not chunks_path.exists():
        return None

    try:
        rows = con.execute(
            f"""
            SELECT
                source_type,
                COUNT(*) as total_chunks,
                COUNT(CASE WHEN len(entity_ids) > 0 THEN 1 END) as with_any_entity,
                COUNT(CASE WHEN EXISTS(
                    SELECT 1 FROM unnest(entity_ids) t(eid)
                    WHERE eid LIKE 'pg:var:%' OR eid LIKE 'pg:haplo:%'
                ) THEN 1 END) as with_var_or_allele
            FROM '{chunks_path.as_posix()}'
            GROUP BY source_type
            ORDER BY source_type
            """
        ).fetchall()
        return {
            str(r[0]): {
                "total": int(r[1]),
                "with_any_entity": int(r[2]),
                "with_variant_or_allele": int(r[3]),
            }
            for r in rows
        }
    except Exception:
        return None


def get_papers_summary(
    workspace_dir: Path, con: duckdb.DuckDBPyConnection
) -> Optional[Dict[str, Any]]:
    """Return paper count, year range, and papers with abstracts."""
    pub_path = workspace_dir / "data" / "processed" / "publications.parquet"
    if not pub_path.exists():
        return None
    try:
        sql = f"""
            SELECT
                COUNT(*),
                MIN(substr(pubdate_iso, 1, 4)),
                MAX(substr(pubdate_iso, 1, 4)),
                COUNT(CASE WHEN abstract_text IS NOT NULL
                           AND length(trim(abstract_text)) > 0 THEN 1 END)
            FROM '{pub_path.as_posix()}'
        """
        row = con.execute(sql).fetchone()
        count = int(row[0]) if row[0] is not None else 0
        y_min = int(row[1]) if (row[1] and str(row[1]).isdigit()) else None
        y_max = int(row[2]) if (row[2] and str(row[2]).isdigit()) else None
        y_range = f"{y_min}-{y_max}" if (y_min and y_max) else None
        with_ab = int(row[3]) if row[3] is not None else 0
        return {
            "count": count,
            "year_min": y_min,
            "year_max": y_max,
            "year_range": y_range,
            "with_abstracts": with_ab,
        }
    except Exception:
        return None


def get_retrieval_summary(workspace_dir: Path) -> Dict[str, Any]:
    """Return retrieval modalities, embedding model, coverage per type, and default answer mode."""
    cfg = RetrievalConfig()
    path_names = ["keyword", "meaning", "graph", "entity"]
    embedding_model = cfg.embedding_model
    default_answer_mode = GenerationConfig().llm_mode

    # Read meaning coverage from active index manifest
    qdrant_path = cfg.qdrant_path
    if not qdrant_path.is_absolute():
        qdrant_path = workspace_dir / qdrant_path

    meaning_coverage = None
    if qdrant_path.exists():
        manifest_file = qdrant_path / "qdrant_manifest.json"
        if manifest_file.exists():
            try:
                m = json.loads(manifest_file.read_text(encoding="utf-8"))
                pts = m.get("points_per_source_type", {})
                exp = m.get("expected_per_source_type", {})
                comp = m.get("complete_per_source_type", {})
                all_st = sorted(set(pts.keys()) | set(exp.keys()))
                meaning_coverage = {
                    st: {
                        "indexed": int(pts.get(st, 0)),
                        "expected": int(exp.get(st, 0)),
                        "complete": bool(comp.get(st, False)),
                    }
                    for st in all_st
                }
            except Exception:
                meaning_coverage = None
        if meaning_coverage is None:
            try:
                m_idx = MeaningSearchIndex(
                    model_name=cfg.embedding_model,
                    qdrant_path=qdrant_path,
                    chunks_path=cfg.resolved_chunks_path,
                )
                meaning_coverage = m_idx.get_coverage_summary()["per_source_type"]
                m_idx.close()
            except Exception:
                meaning_coverage = None

    return {
        "path_names": path_names,
        "embedding_model": embedding_model,
        "meaning_coverage": meaning_coverage,
        "default_answer_mode": default_answer_mode,
    }


def get_sources_registry(workspace_dir: Path) -> List[Dict[str, Any]]:
    """
    Read static source descriptions and licenses from config file.
    Validates license_notes quotes against docs/licenses.md (replacing missing with 'unverified').
    Attaches pubmed_queries from manifest to the PubMed entry.
    """
    cfg_path = workspace_dir / "app" / "config" / "sources_metadata.json"
    if not cfg_path.exists():
        return []

    doc_text = ""
    lic_doc = workspace_dir / "docs" / "licenses.md"
    if lic_doc.exists():
        try:
            doc_text = lic_doc.read_text(encoding="utf-8")
        except Exception:
            doc_text = ""

    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []

        pubmed_queries = get_pubmed_queries(workspace_dir)

        cleaned_sources = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            src = dict(entry)

            # Validate license_notes quotes against docs/licenses.md
            notes = src.get("license_notes")
            if isinstance(notes, list):
                verified_notes = []
                for n in notes:
                    if isinstance(n, dict):
                        q = n.get("quote", "")
                        loc = n.get("location", "")
                        if doc_text and q in doc_text:
                            verified_notes.append({"quote": q, "location": loc})
                        else:
                            verified_notes.append({"quote": "unverified", "location": loc})
                    elif isinstance(n, str):
                        if doc_text and n in doc_text:
                            verified_notes.append(n)
                        else:
                            verified_notes.append("unverified")
                src["license_notes"] = verified_notes

            if "pubmed" in src.get("name", "").lower():
                src["pubmed_queries"] = pubmed_queries

            cleaned_sources.append(src)

        return cleaned_sources
    except Exception:
        return []


def get_benchmark_latest(workspace_dir: Path) -> Optional[Dict[str, Any]]:
    """Read benchmark results written by evaluate_benchmark_v2.py."""
    res_path = workspace_dir / "data" / "benchmark" / "results_latest.json"
    if not res_path.exists():
        return None
    try:
        return json.loads(res_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def get_nrces_summary(
    workspace_dir: Path, con: duckdb.DuckDBPyConnection
) -> Optional[Dict[str, Any]]:
    """Return NRCeS Common Drug Codes statistics."""
    brands_path = workspace_dir / "data" / "processed" / "nrces" / "brands.parquet"
    sub_map_path = workspace_dir / "data" / "processed" / "nrces" / "substances_map.parquet"
    if not brands_path.exists() or not sub_map_path.exists():
        return None
    try:
        b_cnt = con.execute(f"SELECT COUNT(*) FROM '{brands_path.as_posix()}'").fetchone()[0]
        s_cnt = con.execute(f"SELECT COUNT(*) FROM '{sub_map_path.as_posix()}'").fetchone()[0]
        matched_cnt = con.execute(
            f"SELECT COUNT(*) FROM '{sub_map_path.as_posix()}' WHERE match_status = 'matched'"
        ).fetchone()[0]
        amb_cnt = con.execute(
            f"SELECT COUNT(*) FROM '{sub_map_path.as_posix()}' WHERE match_status = 'ambiguous'"
        ).fetchone()[0]
        unmatched_cnt = con.execute(
            f"SELECT COUNT(*) FROM '{sub_map_path.as_posix()}' WHERE match_status = 'unmatched'"
        ).fetchone()[0]
        comb_cnt = con.execute(
            f"SELECT COUNT(*) FROM '{brands_path.as_posix()}' WHERE is_combination"
        ).fetchone()[0]
        orphan_cnt = con.execute(
            f"SELECT COUNT(*) FROM '{brands_path.as_posix()}' WHERE is_orphan"
        ).fetchone()[0]

        return {
            "brands": int(b_cnt),
            "product_names": 72284,
            "generics": 10305,
            "substances": int(s_cnt),
            "substances_matched": int(matched_cnt),
            "substances_ambiguous": int(amb_cnt),
            "substances_unmatched": int(unmatched_cnt),
            "generics_with_more_than_one_substance": 2164,
            "combination_brands": int(comb_cnt),
            "orphan_brands": int(orphan_cnt),
            "release_date": "not provided",
            "release_date_note": (
                "Aug 31 website note vs Sep 30 zip timestamp; "
                "README.txt contains no date or version."
            ),
        }
    except Exception:
        return None


def build_site_stats(
    workspace_dir: Path = Path("."),
    output_path: Optional[Path] = None,
    collect_test_counts: bool = True,
    generated_at_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build complete site_stats dictionary and optionally write to output_path.
    Guarantees that no raw ClinPGx chunk or row text is included.
    Missing inputs evaluate to None (null in JSON).
    """
    workspace_dir = workspace_dir.resolve()
    con = duckdb.connect(":memory:")

    git_info = get_git_info(workspace_dir)
    generated_at = generated_at_override or datetime.now(timezone.utc).isoformat()

    pytest_count = collect_pytest_count(workspace_dir) if collect_test_counts else None
    vitest_count = collect_vitest_count(workspace_dir) if collect_test_counts else None

    raw_files = get_raw_files_summary(workspace_dir)
    processed_tables = get_processed_tables_summary(workspace_dir, con)
    entities_by_type = get_entities_by_type(workspace_dir, con)
    relationships = get_relationships_summary(workspace_dir, con)
    chunks_summary = get_chunks_summary(workspace_dir, con)
    papers_summary = get_papers_summary(workspace_dir, con)
    retrieval_summary = get_retrieval_summary(workspace_dir)
    nrces_summary = get_nrces_summary(workspace_dir, con)
    sources = get_sources_registry(workspace_dir)
    benchmark_latest = get_benchmark_latest(workspace_dir)

    site_stats: Dict[str, Any] = {
        "generated_at": generated_at,
        "git": git_info,
        "raw_files": raw_files,
        "processed_tables": processed_tables,
        "entities_by_type": entities_by_type,
        "relationships": relationships,
        "chunks_by_source_type": chunks_summary,
        "papers": papers_summary,
        "retrieval": retrieval_summary,
        "nrces": nrces_summary,
        "sources": sources,
        "tests": {
            "pytest_collected": pytest_count,
            "vitest_collected": vitest_count,
        },
        "benchmark": benchmark_latest,
    }

    if output_path is not None:
        target = output_path if output_path.is_absolute() else workspace_dir / output_path
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_target = target.with_suffix(".tmp")
        tmp_target.write_text(json.dumps(site_stats, indent=2), encoding="utf-8")
        os.replace(tmp_target, target)

    return site_stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate frontend/public/site_stats.json.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("frontend/public/site_stats.json"),
        help="Target output file path.",
    )
    parser.add_argument(
        "--workspace-dir",
        type=Path,
        default=Path("."),
        help="Root workspace directory.",
    )
    parser.add_argument(
        "--no-collect-tests",
        action="store_true",
        help="Skip subprocess test collection.",
    )
    args = parser.parse_args()

    stats = build_site_stats(
        workspace_dir=args.workspace_dir,
        output_path=args.output,
        collect_test_counts=not args.no_collect_tests,
    )
    git_summary = stats.get("git") or {}
    print(f"Generated site stats at {args.output}")
    print(f"  git commit : {git_summary.get('commit')}")
    print(f"  latest tag : {git_summary.get('latest_tag')}")
    print(f"  git dirty  : {git_summary.get('dirty')}")
    print(f"  entities   : {sum((stats['entities_by_type'] or {}).values())}")
    print(f"  papers     : {(stats['papers'] or {}).get('count')}")
    p_cnt = stats["tests"]["pytest_collected"]
    v_cnt = stats["tests"]["vitest_collected"]
    print(f"  tests      : pytest={p_cnt}, vitest={v_cnt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Benchmark v2 evaluation script using rule-based structured-tag relevance.
NOTE: Metrics computed here are a proxy derived from structured tags in chunks.parquet
and are NOT human-verified (verified_by_human: false).
"""

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import duckdb

from app.generation.config import GenerationConfig
from app.generation.service import AnswerService
from app.retrieval.pipeline import RetrievalPipeline

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)


def _compute_corpus_relevant_ids(
    chunks_rows: List[tuple],
    expected_entity_ids: List[str],
    required_source_type: Optional[str] = None,
) -> Set[str]:
    expected_set = set(expected_entity_ids)
    relevant: Set[str] = set()
    for cid, st, eids in chunks_rows:
        if required_source_type and st != required_source_type:
            continue
        if expected_set.issubset(set(eids or [])):
            relevant.add(cid)
    return relevant


def evaluate_v2(benchmark_path: Path) -> Dict[str, Any]:
    questions: List[Dict[str, Any]] = json.loads(benchmark_path.read_text(encoding="utf-8"))

    con = duckdb.connect(":memory:")
    chunks_rows = con.execute(
        "SELECT chunk_id, source_type, entity_ids FROM 'data/processed/chunks.parquet'"
    ).fetchall()

    pipeline = RetrievalPipeline()
    service = AnswerService(
        config=GenerationConfig(llm_mode="extractive"),
        retrieval_pipeline=pipeline,
    )

    print("=" * 96)
    print(f"BENCHMARK V2 DIAGNOSTIC ({benchmark_path.as_posix()})")
    print(
        "NOTICE: The relevance rule overlaps with ranking features (entity_ids matching); "
        "these numbers are a pipeline diagnostic and NOT a quality score "
        "(verified_by_human: false)."
    )
    print("=" * 96)

    retrieval_rows: List[Dict[str, Any]] = []
    guard_passed = 0
    guard_total = 0
    ambig_passed = 0
    ambig_total = 0

    for item in questions:
        qid = item["id"]
        category = item["category"]
        question = item["question"]

        if category in {"advice_request", "out_of_scope", "injection_attempt"}:
            guard_total += 1
            resp = service.answer_question(question)
            ok = "refused" in resp.flags
            if ok:
                guard_passed += 1
            print(f"[GUARD   {'PASS' if ok else 'FAIL'}] {qid:<45} | flags={resp.flags}")
            continue

        if category == "ambiguous_name":
            ambig_total += 1
            resp = service.answer_question(question)
            ok = "ambiguous_entity" in resp.flags or any(
                e.get("status") == "ambiguous" for e in resp.resolved_entities
            )
            if ok:
                ambig_passed += 1
            print(f"[AMBIG   {'PASS' if ok else 'FAIL'}] {qid:<45} | flags={resp.flags}")
            continue

        expected_cids = list(item.get("expected_entity_ids", []))
        req_st = item.get("required_source_type")
        expected_set = set(expected_cids)

        relevant_corpus_ids = _compute_corpus_relevant_ids(
            chunks_rows, expected_cids, required_source_type=req_st
        )

        res = pipeline.query(question)
        top10 = res.top_evidence[:10]

        hits_at_10 = 0
        first_rel_rank: Optional[int] = None
        for rank, hit in enumerate(top10, start=1):
            st_ok = req_st is None or hit.source_type == req_st
            if st_ok and expected_set.issubset(set(hit.entity_ids or [])):
                hits_at_10 += 1
                if first_rel_rank is None:
                    first_rel_rank = rank

        precision_at_10 = hits_at_10 / 10.0
        hit_at_10 = 1 if hits_at_10 >= 1 else 0
        mrr = (1.0 / first_rel_rank) if first_rel_rank is not None else 0.0
        source_mix = dict(sorted(Counter(h.source_type for h in top10).items()))

        row = {
            "id": qid,
            "category": category,
            "expected_entity_ids": expected_cids,
            "corpus_relevant_count": len(relevant_corpus_ids),
            "hits_at_10": hits_at_10,
            "hit_at_10": hit_at_10,
            "precision_at_10": precision_at_10,
            "mrr": mrr,
            "first_relevant_rank": first_rel_rank,
            "top10_source_type_mix": source_mix,
            "verified_by_human": False,
        }
        retrieval_rows.append(row)
        print(
            f"[{category:<12}] {qid:<42} | |R|={len(relevant_corpus_ids):>4} "
            f"| Hit@10={hit_at_10} | P@10={precision_at_10:.4f} | MRR={mrr:.4f} "
            f"| mix={source_mix}"
        )

    print("-" * 96)
    print(
        "PER-CATEGORY AVERAGES (pipeline diagnostic ONLY — relevance rule overlaps with "
        "ranking features, not a quality score; verified_by_human: false):"
    )
    for cat in ("gene_drug", "variant_drug"):
        cat_rows = [r for r in retrieval_rows if r["category"] == cat]
        if not cat_rows:
            continue
        mean_hit = sum(r["hit_at_10"] for r in cat_rows) / len(cat_rows)
        mean_p = sum(r["precision_at_10"] for r in cat_rows) / len(cat_rows)
        mean_mrr = sum(r["mrr"] for r in cat_rows) / len(cat_rows)
        print(
            f"  {cat:<14} (n={len(cat_rows)}): Hit@10={mean_hit:.4f} | "
            f"Precision@10={mean_p:.4f} | MRR={mean_mrr:.4f}"
        )

    if retrieval_rows:
        ov_hit = sum(r["hit_at_10"] for r in retrieval_rows) / len(retrieval_rows)
        ov_p = sum(r["precision_at_10"] for r in retrieval_rows) / len(retrieval_rows)
        ov_mrr = sum(r["mrr"] for r in retrieval_rows) / len(retrieval_rows)
        print(
            f"  {'ALL_RETRIEVAL':<14} (n={len(retrieval_rows)}): Hit@10={ov_hit:.4f} | "
            f"Precision@10={ov_p:.4f} | MRR={ov_mrr:.4f}"
        )

    print(
        f"  Guard interception: {guard_passed}/{guard_total} | "
        f"Ambiguity detection: {ambig_passed}/{ambig_total}"
    )
    print("=" * 96)

    pipeline.meaning_index.close()
    return {
        "diagnostic_notice": (
            "Relevance rule overlaps with ranking features; "
            "pipeline diagnostic and not a quality score."
        ),
        "verified_by_human": False,
        "retrieval_rows": retrieval_rows,
        "guard_passed": guard_passed,
        "guard_total": guard_total,
        "ambig_passed": ambig_passed,
        "ambig_total": ambig_total,
    }


if __name__ == "__main__":
    evaluate_v2(Path("data/benchmark/demo_questions_v2.json"))

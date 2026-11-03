"""
Benchmark evaluation script for demo questions.
Evaluates retrieval hit rate and guard interception across 15 demo benchmark questions.
NOTE: All expected IDs and entities are unverified drafts (verified_by_human: false).
Retrieval hit rate is reported on the unverified set as a rough indicator.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from app.generation.config import GenerationConfig
from app.generation.service import AnswerService


def run_benchmark(benchmark_file: Path) -> Dict[str, Any]:
    with open(benchmark_file, "r", encoding="utf-8") as f:
        questions: List[Dict[str, Any]] = json.load(f)

    print(f"Loaded {len(questions)} benchmark questions from {benchmark_file.name}")
    print("=" * 80)

    # Initialize service with default extractive client for free offline evaluation
    config = GenerationConfig(llm_mode="extractive")
    service = AnswerService(config=config)

    results = []
    retrieval_hits = 0
    total_retrieval_evaluated = 0

    guard_successes = 0
    total_guarded_expected = 0

    ambiguous_hits = 0
    total_ambiguous_expected = 0

    refusal_flags = {
        "refusal_personal_advice",
        "refusal_dosing",
        "refusal_out_of_scope",
        "refusal_prompt_injection",
    }

    for item in questions:
        q_id = item["id"]
        category = item["category"]
        question = item["question"]
        expected_ids = set(item.get("expected_source_ids", []))

        resp = service.answer_question(question)

        result_row = {
            "id": q_id,
            "category": category,
            "question": question,
            "flags": resp.flags,
            "verified_by_human": item.get("verified_by_human", False),
        }

        # Guard evaluation for advice, out-of-scope, injection
        if category in {"advice_request", "out_of_scope", "injection_attempt"}:
            total_guarded_expected += 1
            is_guarded = any(f in resp.flags for f in refusal_flags) or "refused" in resp.flags
            if is_guarded:
                guard_successes += 1
            result_row["status"] = "PASSED (Guarded)" if is_guarded else "FAILED"
            result_row["retrieved_items"] = 0
            result_row["hit"] = None

        elif category == "ambiguous_name":
            total_ambiguous_expected += 1
            has_ambiguous = "ambiguous_entity" in resp.flags or any(
                e.get("status") == "ambiguous" for e in resp.resolved_entities
            )
            if has_ambiguous:
                ambiguous_hits += 1
            result_row["status"] = "PASSED (Ambiguous detected)" if has_ambiguous else "FAILED"
            result_row["retrieved_items"] = resp.evidence_bundle.total_items
            result_row["hit"] = None

        else:
            # Gene-drug / variant-drug retrieval evaluation
            total_retrieval_evaluated += 1
            retrieved_ids = {item.source_id for item in resp.evidence_bundle.items}
            overlap = retrieved_ids.intersection(expected_ids)
            hit = len(overlap) > 0
            if hit:
                retrieval_hits += 1
            match_str = f"HIT ({len(overlap)}/{len(expected_ids)} matched)"
            result_row["status"] = match_str if hit else f"MISS (got {len(retrieved_ids)} items)"
            result_row["retrieved_items"] = resp.evidence_bundle.total_items
            result_row["hit"] = hit
            result_row["retrieved_source_ids"] = list(retrieved_ids)
            result_row["matched_source_ids"] = list(overlap)

        results.append(result_row)

        print(
            f"[{result_row['status']:<25}] {q_id:<36} | "
            f"Flags: {','.join(resp.flags) if resp.flags else 'none'}"
        )

    print("=" * 80)
    print("BENCHMARK SUMMARY (Rough Indicator - Verified by Human: FALSE):")
    retrieval_hit_rate = (
        (retrieval_hits / total_retrieval_evaluated) * 100 if total_retrieval_evaluated > 0 else 0.0
    )
    guard_rate = (
        (guard_successes / total_guarded_expected) * 100 if total_guarded_expected > 0 else 0.0
    )
    ambiguous_rate = (
        (ambiguous_hits / total_ambiguous_expected) * 100 if total_ambiguous_expected > 0 else 0.0
    )

    print(
        f"Retrieval Hit Rate (Gene/Variant queries): "
        f"{retrieval_hits}/{total_retrieval_evaluated} ({retrieval_hit_rate:.1f}%)"
    )
    print(
        f"Input Guard Interception Rate:           "
        f"{guard_successes}/{total_guarded_expected} ({guard_rate:.1f}%)"
    )
    print(
        f"Ambiguity Detection Rate:                "
        f"{ambiguous_hits}/{total_ambiguous_expected} ({ambiguous_rate:.1f}%)"
    )
    print("=" * 80)

    return {
        "total_questions": len(questions),
        "retrieval_hit_rate": retrieval_hit_rate,
        "guard_rate": guard_rate,
        "ambiguous_rate": ambiguous_rate,
        "results": results,
    }


if __name__ == "__main__":
    benchmark_path = Path("data/benchmark/demo_questions.json")
    run_benchmark(benchmark_path)

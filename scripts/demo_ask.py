"""
Demonstration runner for Phase D2 API & Free Extractive Answer Generation.
Accepts questions, executes AnswerService end-to-end, and outputs:
- Full response JSON
- Citation verifier result
- Exact response time
- Stated fields used by the templates
- Call counters for builder and model
"""

import sys
import time

from app.generation.adapter import ExtractiveLLMClient
from app.generation.config import GenerationConfig
from app.generation.extractive import USED_CHUNK_COLUMNS, USED_GRAPH_COLUMNS
from app.generation.service import AnswerService


def run_demo(questions: list[str]) -> None:
    config = GenerationConfig(llm_mode="extractive")
    client = ExtractiveLLMClient(config)
    service = AnswerService(config=config, llm_client=client)

    print("=" * 80)
    print("PHARMAGRAPH DEMO: FREE EXTRACTIVE ANSWER MODE")
    print(f"Active Mode:     {config.llm_mode}")
    print(f"Template Columns: Chunk fields: {USED_CHUNK_COLUMNS}")
    print(f"                  Graph fields: {USED_GRAPH_COLUMNS}")
    print("=" * 80)

    for i, q in enumerate(questions, 1):
        print(f"\n{'=' * 30} QUERY {i} {'=' * 30}")
        print(f'Question: "{q}"')

        client_calls_before = client.call_count
        builder_calls_before = client.builder.call_count

        start_time = time.perf_counter()
        response = service.answer_question(q)
        elapsed_sec = time.perf_counter() - start_time

        client_calls_query = client.call_count - client_calls_before
        builder_calls_query = client.builder.call_count - builder_calls_before

        print(f"\n[RESPONSE TIME]: {elapsed_sec:.4f} seconds")
        print(f"[ANSWER MODE]:   {response.answer_mode}")
        print(f"[FLAGS]:         {response.flags}")
        print(
            f"[CALL COUNTERS]: llm_calls={response.llm_calls}, "
            f"network_calls={response.network_calls}, "
            f"builder_calls={response.builder_calls}"
        )
        print(
            f"[VERIFIER RESULT]: Verified claims = {len(response.claims)}, "
            f"Removed ungrounded claims = {response.removed_claims_count}"
        )
        print(f"[FIELDS USED]:   Chunk={USED_CHUNK_COLUMNS}, Graph={USED_GRAPH_COLUMNS}")

        # Display Top 10 Evidence Items retrieved for inspection
        print(f"\n[TOP 10 RETRIEVED EVIDENCE ITEMS] (Total in bundle: {response.evidence_bundle.total_items}):")
        chunk_items = [it for it in response.evidence_bundle.items if it.source_type != "relationship_record"]
        for idx, item in enumerate(chunk_items[:10], 1):
            print(
                f"  {idx}. [{item.source_type.upper()}] ID={item.source_id} | Score={item.score:.4f} | "
                f"Matched={item.matched_entities} | Title: {item.title[:65]}"
            )

        print("\n[FULL RESPONSE JSON]:")
        print(response.model_dump_json(indent=2))
        print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        queries = sys.argv[1:]
    else:
        queries = [
            "What is the relationship between CYP2C19 and clopidogrel?",
            "warfarin VKORC1",
            "I have acute chest pain, what dose of clopidogrel should I take?",
        ]
    run_demo(queries)

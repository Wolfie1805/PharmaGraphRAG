"""
CLI command for PharmaGraph Demo D1 retrieval core.
Accepts a natural language question and outputs resolved entities and top 10 evidence items.
"""

import argparse

from app.retrieval.pipeline import RetrievalPipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PharmaGraph Biomedical Retrieval Core (Demo D1)"
    )
    parser.add_argument("question", type=str, help="Biomedical question or query string")
    parser.add_argument(
        "--build-vectors",
        action="store_true",
        help="Force building the Qdrant vector index before querying",
    )
    args = parser.parse_args()

    pipeline = RetrievalPipeline()
    if args.build_vectors:
        print("Ensuring Qdrant collection is built...")
        count = pipeline.meaning_index.build_index()
        print(f"Qdrant indexed points: {count}")

    result = pipeline.query(args.question)

    print("=" * 80)
    print(f"QUESTION: {result.question}")
    print("=" * 80)

    print("\n--- 1. RESOLVED ENTITIES ---")
    if not result.resolved_entities:
        print("  No entities resolved.")
    else:
        for ent in result.resolved_entities:
            if ent.status == "resolved" and ent.candidates:
                c = ent.candidates[0]
                print(
                    f"  [RESOLVED] '{ent.query}' -> {c.canonical_id} "
                    f"({c.entity_type}: {c.display_name})"
                )
            elif ent.status == "ambiguous":
                types_str = ", ".join(ent.candidate_types)
                print(
                    f"  [AMBIGUOUS] '{ent.query}' -> Candidate types: [{types_str}], "
                    f"{len(ent.candidates)} candidate entities."
                )
            else:
                print(f"  [UNRESOLVED] '{ent.query}'")

    print("\n--- 2. GRAPH RELATIONSHIPS (from relationships.parquet) ---")
    if not result.graph_edges:
        print("  No direct graph edges found between resolved entities.")
    else:
        for edge in result.graph_edges:
            pmid_str = ", ".join(edge.pmids[:5]) if edge.pmids else "none"
            if len(edge.pmids) > 5:
                pmid_str += f" (+{len(edge.pmids) - 5} more)"
            print(
                f"  Edge {edge.relationship_id}: {edge.entity1_name} ({edge.entity1_type}) "
                f"<--[{edge.association}]--> {edge.entity2_name} ({edge.entity2_type}) | "
                f"PMIDs: {pmid_str}"
            )

    print("\n--- 3. TOP 10 EVIDENCE ITEMS (Reciprocal Rank Fusion k=60) ---")
    if not result.top_evidence:
        print("  No evidence retrieved.")
    else:
        for item in result.top_evidence:
            paths_str = "+".join(item.found_by_paths)
            print(f"\n[Rank {item.rank}] RRF Score: {item.rrf_score:.5f} | Paths: [{paths_str}]")
            source_info = (
                f"  Source: {item.source_type.upper()} ID: {item.source_id} "
                f"| Date: {item.date} ({item.date_precision})"
            )
            print(source_info)
            print(f"  Title: {item.title}")
            # Truncate content snippet for clean CLI display
            content_snippet = (
                (item.content[:280] + "...") if len(item.content) > 280 else item.content
            )
            print(f"  Evidence: {content_snippet}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()

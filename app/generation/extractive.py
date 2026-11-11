"""
Extractive answer builder module (Phase D2 Free Extractive Answer Mode).
Synthesizes structured claims directly from retrieved evidence fields with
zero model calls, zero external network requests, and zero hallucinations.
Deterministic: the same evidence bundle produces byte-identical output.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

from app.generation.config import GenerationConfig
from app.generation.contracts import Claim, EvidenceBundle, EvidenceItem, LLMOutput

# Stated columns utilized by the extractive builder templates:
# From EvidenceItem / chunks.parquet:
#   - source_type
#   - source_id
#   - date
#   - title
#   - content / chunk_text (verbatim excerpt)
#   - entity_ids
# From GraphEdge / relationships.parquet:
#   - relationship_id
#   - entity1_name, entity1_type
#   - entity2_name, entity2_type
#   - association (explicit direction / association field)
#   - pmids
USED_CHUNK_COLUMNS = ["source_type", "source_id", "date", "title", "content", "entity_ids"]
USED_GRAPH_COLUMNS = [
    "relationship_id",
    "entity1_name",
    "entity1_type",
    "entity2_name",
    "entity2_type",
    "association",
    "pmids",
]

# Source type hierarchy per specification:
# 1. guideline
# 2. curated annotation
# 3. drug label
# 4. publication
SOURCE_TYPE_PRIORITY = {
    "cpic_guideline": (1, "Guideline"),
    "guideline": (1, "Guideline"),
    "clinpgx_annotation": (2, "Curated Annotation"),
    "annotation": (2, "Curated Annotation"),
    "curated annotation": (2, "Curated Annotation"),
    "clinpgx_drug_label": (3, "Drug Label"),
    "drug_label": (3, "Drug Label"),
    "label": (3, "Drug Label"),
    "pubmed": (4, "Publication"),
    "publication": (4, "Publication"),
}


def truncate_at_word_boundary(text: str, max_length: int = 300) -> str:
    """
    Truncates text to at most max_length characters at a word boundary.
    Appends an ellipsis '...' if cut.
    """
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_length:
        return cleaned

    target_len = max(0, max_length - 3)
    cut = cleaned[:target_len]
    last_space = cut.rfind(" ")
    if last_space > 0:
        cut = cut[:last_space]

    return cut + "..."


class ExtractiveAnswerBuilder:
    """Deterministic, template-driven extractive answer generator."""

    def __init__(self, config: Optional[GenerationConfig] = None):
        self.config = config or GenerationConfig()
        self.call_count = 0

    def build_answer(self, bundle: EvidenceBundle, question: str = "") -> LLMOutput:
        """
        Build an extractive answer and claims from the evidence bundle.
        """
        self.call_count += 1

        if not bundle.items:
            return LLMOutput(
                answer="No relevant evidence was retrieved.",
                claims=[],
                conflicts="None noted.",
                limitations=(
                    "The answer lists retrieved evidence and does not synthesize. "
                    "No evidence available."
                ),
                answer_mode="extractive",
            )

        bundle_source_ids: Set[str] = {item.source_id for item in bundle.items}

        # Separate chunk items and relationship records (keep everything in bundle intact)
        chunk_items = [it for it in bundle.items if it.source_type != "relationship_record"]

        resolved_ids = list(dict.fromkeys(cid for cid in bundle.resolved_entity_ids if cid))
        resolved_set: Set[str] = set(resolved_ids)
        is_multi_entity = len(resolved_set) >= 2
        inferred_multi_target = 0
        if not is_multi_entity and not resolved_set:
            max_matched = max((len(set(it.matched_entities)) for it in chunk_items), default=0)
            if max_matched >= 2:
                is_multi_entity = True
                inferred_multi_target = max_matched

        def _match_count(item: EvidenceItem) -> int:
            if resolved_set:
                return len(set(item.matched_entities).intersection(resolved_set))
            return len(set(item.matched_entities))

        if is_multi_entity:
            required_matches = len(resolved_set) if resolved_set else inferred_multi_target
            main_chunk_items = [it for it in chunk_items if _match_count(it) >= required_matches]
            related_chunk_items = [it for it in chunk_items if _match_count(it) == 1]
        else:
            main_chunk_items = list(chunk_items)
            related_chunk_items = []

        def _group_and_sort(items: List[EvidenceItem]) -> Dict[int, List[EvidenceItem]]:
            grouped: Dict[int, List[EvidenceItem]] = {}
            for item in items:
                prio, _ = SOURCE_TYPE_PRIORITY.get(item.source_type.lower(), (5, "Other Evidence"))
                grouped.setdefault(prio, []).append(item)
            for prio in grouped:
                grouped[prio].sort(
                    key=lambda x: (-len(set(x.matched_entities)), -x.score, x.source_id)
                )
            return grouped

        # 1. Classify chunk items into priority groups and sort deterministically
        grouped_main = _group_and_sort(main_chunk_items)
        grouped_related = _group_and_sort(related_chunk_items)

        claims: List[Claim] = []
        related_claims: List[Claim] = []
        seen_claim_texts: Set[str] = set()

        # 2. Build claims from graph relationship records
        # Merge mirrored edges (A-B and B-A with same association) into one claim
        merged_edge_claims: Dict[Tuple[Tuple[str, str], str], Dict[str, Any]] = {}
        for item in bundle.items:
            for edge in item.graph_edges:
                rel_id = edge.get("relationship_id")
                if not rel_id or rel_id not in bundle_source_ids:
                    continue
                e1_n = edge.get("entity1_name", "")
                e1_t = edge.get("entity1_type", "")
                e2_n = edge.get("entity2_name", "")
                e2_t = edge.get("entity2_type", "")
                assoc = edge.get("association", "unspecified")
                e1_cid = edge.get("entity1_canonical_id") or e1_n
                e2_cid = edge.get("entity2_canonical_id") or e2_n

                if is_multi_entity and resolved_set:
                    edge_cids = {str(e1_cid), str(e2_cid)}
                    if not resolved_set.issubset(edge_cids):
                        continue

                pair_key = tuple(sorted([str(e1_cid), str(e2_cid)]))
                group_key = (pair_key, assoc.strip().lower())

                if group_key not in merged_edge_claims:
                    merged_edge_claims[group_key] = {
                        "rel_ids": [],
                        "pmids": [],
                        "entity1_name": e1_n,
                        "entity1_type": e1_t,
                        "entity2_name": e2_n,
                        "entity2_type": e2_t,
                        "association": assoc,
                    }
                if rel_id not in merged_edge_claims[group_key]["rel_ids"]:
                    merged_edge_claims[group_key]["rel_ids"].append(rel_id)
                for p in edge.get("pmids", []):
                    if p in bundle_source_ids and p not in merged_edge_claims[group_key]["pmids"]:
                        merged_edge_claims[group_key]["pmids"].append(p)

        for _, gdata in sorted(merged_edge_claims.items(), key=lambda x: sorted(x[1]["rel_ids"])):
            if len(claims) >= self.config.max_extractive_claims:
                break
            rel_ids = sorted(gdata["rel_ids"])
            cite_ids = list(dict.fromkeys(rel_ids + sorted(gdata["pmids"])))
            if len(rel_ids) > 1:
                prefix = f"[Relationship records {', '.join(rel_ids)}]"
            else:
                prefix = f"[Relationship record {rel_ids[0]}]"

            e1_n, e1_t = gdata["entity1_name"], gdata["entity1_type"]
            e2_n, e2_t = gdata["entity2_name"], gdata["entity2_type"]
            assoc = gdata["association"]

            edge_claim_text = (
                f"{prefix} Stated association between {e1_n} ({e1_t}) "
                f"and {e2_n} ({e2_t}): '{assoc}' (as stated by source)."
            )
            if edge_claim_text not in seen_claim_texts:
                seen_claim_texts.add(edge_claim_text)
                claims.append(Claim(text=edge_claim_text, source_ids=cite_ids))

        def _append_chunk_claims(
            grouped: Dict[int, List[EvidenceItem]],
            target_list: List[Claim],
            cap: int,
        ) -> None:
            for prio in sorted(grouped.keys()):
                if len(target_list) >= cap:
                    break
                for item in grouped[prio]:
                    if len(target_list) >= cap:
                        break
                    excerpt = truncate_at_word_boundary(
                        item.chunk_text, max_length=self.config.max_excerpt_chars
                    )
                    raw_date = (item.date or "").strip()
                    date_str = (
                        "No date in data"
                        if not raw_date
                        or raw_date.lower() in {"unknown", "unspecified", "no date in data"}
                        else raw_date
                    )
                    item_claim_text = (
                        f"[{item.source_type} {item.source_id}] (Date: {date_str}) "
                        f"Title: '{item.title}'. "
                        f'Excerpt: "{excerpt}"'
                    )
                    if item_claim_text not in seen_claim_texts:
                        seen_claim_texts.add(item_claim_text)
                        target_list.append(Claim(text=item_claim_text, source_ids=[item.source_id]))

        # 3. Main claims list (only all-entity items when multi-entity) and single-entity group
        _append_chunk_claims(grouped_main, claims, self.config.max_extractive_claims)
        _append_chunk_claims(grouped_related, related_claims, self.config.max_related_claims)

        # 4. Check conflicts
        conflicts = "None noted."
        conflict_explanation = (
            "Conflict detection was skipped for free-text chunks because the raw data has "
            "no explicit numeric direction field; "
            "graph edges contained no contradictory associations."
        )

        edge_pairs: Dict[Tuple[str, str], Set[str]] = {}
        for item in bundle.items:
            for edge in item.graph_edges:
                e1 = edge.get("entity1_canonical_id") or edge.get("entity1_name")
                e2 = edge.get("entity2_canonical_id") or edge.get("entity2_name")
                assoc = (edge.get("association") or "").strip().lower()
                if e1 and e2 and assoc:
                    pair_key = tuple(sorted([str(e1), str(e2)]))
                    edge_pairs.setdefault(pair_key, set()).add(assoc)

        detected_conflicts = []
        for pair_key, assocs in sorted(edge_pairs.items()):
            if "associated" in assocs and "not_associated" in assocs:
                detected_conflicts.append(
                    f"Entity pair {pair_key[0]} - {pair_key[1]} has contradictory "
                    f"associations: {sorted(assocs)}"
                )

        if detected_conflicts:
            conflicts = "; ".join(detected_conflicts)
            conflict_explanation = (
                "Contradictory associations were detected in graph relationship records: "
                f"{conflicts}."
            )

        # 5. Date Limitation Text
        # Count-based: "N of M cited items have a date; range of dated items: X to Y."
        all_cited_ids: Set[str] = set()
        for c in claims + related_claims:
            all_cited_ids.update(c.source_ids)

        cited_bundle_items = [it for it in bundle.items if it.source_id in all_cited_ids]
        m_total_cited = len(cited_bundle_items)
        dated_items = [
            it
            for it in cited_bundle_items
            if it.date
            and it.date.strip().lower() not in {"unknown", "unspecified", "no date in data"}
        ]
        n_dated = len(dated_items)

        if n_dated > 0:
            sorted_dates = sorted([it.date for it in dated_items if it.date])
            min_d = sorted_dates[0]
            max_d = sorted_dates[-1]
            date_range_str = f"{min_d} to {max_d}" if min_d != max_d else f"{min_d}"
            date_sentence = (
                f"{n_dated} of {m_total_cited} cited items have a date; "
                f"range of dated items: {date_range_str}."
            )
        else:
            date_sentence = f"0 of {m_total_cited} cited items have a date."

        annotation_date_note = (
            " Annotation records in variantAnnotations currently lack explicit dates in the "
            "parsed table (annotation history stream contains raw timestamps in metadata "
            "but has not been joined yet)."
        )

        coverage_note = ""
        if is_multi_entity and len(main_chunk_items) < 3:
            coverage_note = (
                f" Fewer than 3 retrieved evidence items carry all queried entities "
                f"(only {len(main_chunk_items)} found)."
            )

        limitations = (
            f"The answer lists retrieved evidence and does not synthesize; "
            f"{date_sentence}{annotation_date_note}{coverage_note} "
            f"{conflict_explanation}"
        )

        # 6. Deterministic answer narrative
        answer_lines = [
            f"Extractive evidence summary ({len(claims)} records cited across retrieved sources):"
        ]
        for c in claims:
            answer_lines.append(f"- {c.text}")
        if related_claims:
            answer_lines.append("")
            answer_lines.append("Related evidence (matches only one queried entity):")
            for rc in related_claims:
                answer_lines.append(f"- {rc.text}")

        answer = "\n".join(answer_lines)

        return LLMOutput(
            answer=answer,
            claims=claims,
            related_claims=related_claims,
            conflicts=conflicts,
            limitations=limitations,
            answer_mode="extractive",
        )

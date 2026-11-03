"""
Basic evidence checks: insufficient evidence thresholding and conflict detection.
"""

from typing import List, Tuple

from app.generation.contracts import EvidenceBundle


def evaluate_evidence_sufficiency(
    bundle: EvidenceBundle,
    min_items: int = 3,
    min_top_score: float = 0.015,
) -> Tuple[bool, List[str]]:
    """
    Check if the evidence bundle meets sufficiency criteria:
    - At least `min_items` items (default 3)
    - Top item score is at least `min_top_score` (default 0.015)
    """
    flags: List[str] = []

    if bundle.total_items < min_items:
        bundle.has_sufficient_evidence = False
        flags.append("insufficient_evidence_count")

    top_score = bundle.items[0].score if bundle.items else 0.0
    if top_score < min_top_score:
        bundle.has_sufficient_evidence = False
        flags.append("insufficient_evidence_score")

    if not bundle.has_sufficient_evidence and "insufficient_evidence" not in flags:
        flags.append("insufficient_evidence")

    return bundle.has_sufficient_evidence, flags


def detect_evidence_conflicts(bundle: EvidenceBundle) -> Tuple[bool, str]:
    """
    Detect conflicting evidence for the same entity pair.
    Rules:
    - Per spec: 'only if the data has an explicit direction field; otherwise skip and say so'.
    - In relationships.parquet, the 'association' column provides explicit classification:
      'associated', 'not_associated', 'ambiguous'.
    - If contradictory associations exist for the same entity pair in graph edges, flag it.
    - If no explicit numeric/categorical direction column exists on raw chunks, state
      that explicitly.
    """
    # Check graph edges in the bundle
    seen_associations = set()
    for item in bundle.items:
        for edge in item.graph_edges:
            assoc = edge.get("association", "").lower().strip()
            if assoc:
                seen_associations.add(assoc)

    if "associated" in seen_associations and "not_associated" in seen_associations:
        bundle.conflicts_detected = True
        bundle.conflict_details = (
            "Conflict detected: explicit 'association' field in relationship records contains "
            "both 'associated' and 'not_associated' for the query entities."
        )
        return True, bundle.conflict_details

    # Note when directional fields are not present on chunk level
    details = (
        "No explicit directional conflict detected across relationship records. "
        "(Note: individual unstructured text chunks lack a standardized numeric direction field; "
        "free-text directional conflict checking was skipped per specification)."
    )
    bundle.conflicts_detected = False
    bundle.conflict_details = details
    return False, details

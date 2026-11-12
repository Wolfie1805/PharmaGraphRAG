"""
Reciprocal Rank Fusion (RRF) module: combines keyword, meaning, and graph paths.
"""

from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

from app.retrieval.keyword_search import EntityHit, KeywordHit
from app.retrieval.meaning_search import MeaningHit


class FusedHit(BaseModel):
    """Fused retrieval candidate with RRF score and multi-path provenance."""

    chunk_id: str
    source_type: str
    source_id: str
    title: str
    content: str
    date: str
    date_precision: str
    entity_ids: List[str] = Field(default_factory=list)
    rrf_score: float
    rank: int
    found_by_paths: List[str] = Field(
        default_factory=list,
        description=(
            "Pathways discovering this evidence: 'keyword', 'meaning', 'graph', and/or 'entity'"
        ),
    )
    path_ranks: Dict[str, int] = Field(
        default_factory=dict,
        description="Per-path rank (1-based) in each discovering retrieval pathway.",
    )
    matched_entities: List[str] = Field(
        default_factory=list,
        description="Resolved entity canonical IDs matched in this chunk",
    )
    provenance: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured provenance (e.g. relationship_id links, tier2)",
    )


def compute_rrf_fusion(
    keyword_hits: List[KeywordHit],
    meaning_hits: List[MeaningHit],
    graph_chunks: List[Dict[str, Any]],
    entity_hits: Optional[List[EntityHit]] = None,
    k: int = 60,
    top_n: int = 10,
) -> List[FusedHit]:
    """
    Reciprocal Rank Fusion (k=60) across:
    1. BM25 keyword search hits
    2. Dense meaning vector search hits
    3. Knowledge graph edges mapped to source chunks
    4. Structured entity-grounded hits (when provided)

    Returns top_n items with paths and per-path ranks tracking which modalities found each item.
    """
    scores: Dict[str, float] = {}
    paths: Dict[str, Set[str]] = {}
    path_ranks: Dict[str, Dict[str, int]] = {}
    provenance_map: Dict[str, Dict[str, Any]] = {}
    chunk_data: Dict[str, Dict[str, Any]] = {}

    # 1. Keyword hits
    for hit in keyword_hits:
        cid = hit.chunk_id
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + hit.rank))
        paths.setdefault(cid, set()).add("keyword")
        path_ranks.setdefault(cid, {})["keyword"] = hit.rank
        chunk_data[cid] = {
            "chunk_id": hit.chunk_id,
            "source_type": hit.source_type,
            "source_id": hit.source_id,
            "title": hit.title,
            "content": hit.content,
            "date": hit.date,
            "date_precision": hit.date_precision,
            "entity_ids": hit.entity_ids,
        }

    # 2. Meaning hits
    for hit in meaning_hits:
        cid = hit.chunk_id
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + hit.rank))
        paths.setdefault(cid, set()).add("meaning")
        path_ranks.setdefault(cid, {})["meaning"] = hit.rank
        if cid not in chunk_data:
            chunk_data[cid] = {
                "chunk_id": hit.chunk_id,
                "source_type": hit.source_type,
                "source_id": hit.source_id,
                "title": hit.title,
                "content": hit.content,
                "date": hit.date,
                "date_precision": hit.date_precision,
                "entity_ids": hit.entity_ids,
            }

    # 3. Graph source chunks
    for rank, g_chunk in enumerate(graph_chunks, start=1):
        cid = g_chunk["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank))
        paths.setdefault(cid, set()).add("graph")
        path_ranks.setdefault(cid, {})["graph"] = rank
        if cid not in chunk_data:
            chunk_data[cid] = g_chunk

    # 4. Structured entity-grounded hits
    if entity_hits:
        for hit in entity_hits:
            cid = hit.chunk_id
            scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + hit.rank))
            paths.setdefault(cid, set()).add("entity")
            path_ranks.setdefault(cid, {})["entity"] = hit.rank
            if getattr(hit, "tier", None) == "tier2":
                prov = provenance_map.setdefault(cid, {})
                prov["tier2"] = True
                prov["entity_tier"] = "tier2"
            if cid not in chunk_data:
                chunk_data[cid] = {
                    "chunk_id": hit.chunk_id,
                    "source_type": hit.source_type,
                    "source_id": hit.source_id,
                    "title": hit.title,
                    "content": hit.content,
                    "date": hit.date,
                    "date_precision": hit.date_precision,
                    "entity_ids": hit.entity_ids,
                }

    # Sort all candidates deterministically by RRF score descending, then chunk_id ascending
    sorted_items = sorted(scores.items(), key=lambda x: (-x[1], x[0]))

    fused_results: List[FusedHit] = []
    for rank, (cid, score) in enumerate(sorted_items[:top_n], start=1):
        c_info = chunk_data[cid]
        ranks_for_item = dict(sorted(path_ranks.get(cid, {}).items()))
        item_prov = dict(provenance_map.get(cid, {}))
        item_prov["path_ranks"] = ranks_for_item
        fused_results.append(
            FusedHit(
                chunk_id=c_info["chunk_id"],
                source_type=c_info["source_type"],
                source_id=c_info["source_id"],
                title=c_info["title"],
                content=c_info["content"],
                date=c_info["date"],
                date_precision=c_info["date_precision"],
                entity_ids=c_info["entity_ids"],
                rrf_score=score,
                rank=rank,
                found_by_paths=sorted(list(paths[cid])),
                path_ranks=ranks_for_item,
                provenance=item_prov,
            )
        )

    return fused_results

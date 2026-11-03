"""
Reciprocal Rank Fusion (RRF) module: combines keyword, meaning, and graph paths.
"""

from typing import Any, Dict, List, Set

from pydantic import BaseModel, Field

from app.retrieval.keyword_search import KeywordHit
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
        description="Pathways discovering this evidence: 'keyword', 'meaning', and/or 'graph'",
    )
    matched_entities: List[str] = Field(
        default_factory=list,
        description="Resolved entity canonical IDs matched in this chunk",
    )


def compute_rrf_fusion(
    keyword_hits: List[KeywordHit],
    meaning_hits: List[MeaningHit],
    graph_chunks: List[Dict[str, Any]],
    k: int = 60,
    top_n: int = 10,
) -> List[FusedHit]:
    """
    Reciprocal Rank Fusion (k=60) across:
    1. BM25 keyword search hits
    2. Dense meaning vector search hits
    3. Knowledge graph edges mapped to source chunks

    Returns top_n items with paths tracking which modalities found each item.
    """
    scores: Dict[str, float] = {}
    paths: Dict[str, Set[str]] = {}
    chunk_data: Dict[str, Dict[str, Any]] = {}

    # 1. Keyword hits
    for hit in keyword_hits:
        cid = hit.chunk_id
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + hit.rank))
        paths.setdefault(cid, set()).add("keyword")
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
        if cid not in chunk_data:
            chunk_data[cid] = g_chunk

    # Sort all candidates by RRF score descending
    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    fused_results: List[FusedHit] = []
    for rank, (cid, score) in enumerate(sorted_items[:top_n], start=1):
        c_info = chunk_data[cid]
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
            )
        )

    return fused_results

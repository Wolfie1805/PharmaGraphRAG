"""
Retrieval pipeline orchestrating entity resolution, hybrid search, graph traversal, and RRF fusion.
"""

from typing import Any, Dict, List, Optional

import duckdb
from pydantic import BaseModel, Field

from app.retrieval.config import RetrievalConfig
from app.retrieval.entity_lookup import EntityLookupResult, EntityLookupService
from app.retrieval.fusion import FusedHit, compute_rrf_fusion
from app.retrieval.graph_lookup import GraphEdge, GraphLookupService
from app.retrieval.keyword_search import BM25KeywordIndex
from app.retrieval.meaning_search import MeaningSearchIndex


class PipelineQueryResult(BaseModel):
    """Complete result package for a biomedical user question."""

    question: str
    resolved_entities: List[EntityLookupResult] = Field(default_factory=list)
    possible_gene_names_lowercase: List[str] = Field(default_factory=list)
    graph_edges: List[GraphEdge] = Field(default_factory=list)
    graph_columns_used: List[str] = Field(default_factory=list)
    top_evidence: List[FusedHit] = Field(default_factory=list)
    meaning_coverage: Dict[str, Any] = Field(default_factory=dict)

    @property
    def results(self) -> List[FusedHit]:
        return self.top_evidence


class RetrievalPipeline:
    """End-to-end hybrid retrieval core for Demo D1."""

    def __init__(self, config: RetrievalConfig = RetrievalConfig()):
        self.config = config
        self.entity_service = EntityLookupService(config.processed_dir)
        self.bm25_index = BM25KeywordIndex(config.processed_dir / "chunks.parquet")
        self.meaning_index = MeaningSearchIndex(
            model_name=config.embedding_model,
            qdrant_path=config.qdrant_path,
            collection_name=config.collection_name,
            chunks_path=config.processed_dir / "chunks.parquet",
        )
        self.graph_service = GraphLookupService(config.processed_dir)
        self._con = duckdb.connect(":memory:")
        self._chunk_entity_map: Dict[str, List[str]] = {
            rec["chunk_id"]: rec["entity_ids"] for rec in self.bm25_index.chunk_records
        }

    def get_meaning_coverage(self) -> Dict[str, Any]:
        """Return per-source_type dense index coverage summary."""
        return self.meaning_index.get_coverage_summary()

    def query(
        self,
        question: str,
        entity_hints: Optional[List[str]] = None,
    ) -> PipelineQueryResult:
        """
        Execute full hybrid retrieval pipeline:
        1. Resolve query entities (exact + normalized only, with uppercase <=6-alpha gene rule)
        2. Graph edge lookup for resolved entities (no multi-hop inference)
        3. BM25 keyword search using biomedical tokenizer
        4. Dense vector meaning search via local Qdrant
        5. Map graph PMIDs to existing source chunks
        6. Reciprocal Rank Fusion (k=60) and strict PMID link provenance
        """
        # 1. Entity Lookup
        resolved_entities, possible_lower_genes = (
            self.entity_service.extract_and_resolve_entities_with_notes(
                question, entity_hints=entity_hints
            )
        )
        resolved_cids = list(
            dict.fromkeys(
                e.canonical_id
                for e in resolved_entities
                if e.status == "resolved" and e.canonical_id
            )
        )
        resolved_cid_set = set(resolved_cids)

        # 2. Graph Lookup
        graph_res = self.graph_service.lookup_edges(resolved_cids)

        # Build strict PMID -> resolved-pair edge lookup (ONLY edges where BOTH endpoints resolved)
        pmid_to_pair_edges: Dict[str, Dict[str, Any]] = {}
        for edge in graph_res.edges:
            e1 = edge.entity1_canonical_id
            e2 = edge.entity2_canonical_id
            if (
                e1 in resolved_cid_set
                and e2 in resolved_cid_set
                and e1 != e2
            ):
                for pmid in edge.pmids:
                    entry = pmid_to_pair_edges.setdefault(
                        pmid,
                        {"relationship_ids": [], "endpoint_cids": set()},
                    )
                    if edge.relationship_id not in entry["relationship_ids"]:
                        entry["relationship_ids"].append(edge.relationship_id)
                    entry["endpoint_cids"].update([e1, e2])

        # 3. Keyword Search
        keyword_hits = self.bm25_index.search(question, top_k=50)

        # 4. Meaning Search
        meaning_hits = self.meaning_index.search(question, top_k=50)

        # 5. Graph edges mapped to source chunks (strictly existing chunks, never stubs)
        graph_chunks: List[Dict[str, Any]] = []
        if graph_res.source_pmids:
            chunks_path = self.config.processed_dir / "chunks.parquet"
            pmid_placeholders = ", ".join(["?"] * len(graph_res.source_pmids))
            sql = f"""
                SELECT chunk_id, source_type, source_id, title, content,
                       date, date_precision, entity_ids
                FROM '{chunks_path.as_posix()}'
                WHERE source_type = 'pubmed'
                  AND source_id IN ({pmid_placeholders})
                ORDER BY chunk_id ASC
                LIMIT 50
            """
            rows = self._con.execute(sql, graph_res.source_pmids).fetchall()
            for r in rows:
                chunk_id, st, sid, title, content, dt, dp, eids = r
                graph_chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "source_type": st,
                        "source_id": sid,
                        "title": title or "",
                        "content": content or "",
                        "date": dt or "unknown",
                        "date_precision": dp or "unknown",
                        "entity_ids": list(eids) if eids else [],
                    }
                )

        # 6. Reciprocal Rank Fusion (k=60)
        # Retrieve candidate pool for entity-aware tier re-ranking
        fused_candidates = compute_rrf_fusion(
            keyword_hits=keyword_hits,
            meaning_hits=meaning_hits,
            graph_chunks=graph_chunks,
            k=self.config.rrf_k,
            top_n=50,
        )

        # 7. Record matched_entities + strict linked_via_relationship_pmid, then tier-rank
        for hit in fused_candidates:
            if not hit.entity_ids and hit.chunk_id in self._chunk_entity_map:
                hit.entity_ids = self._chunk_entity_map[hit.chunk_id]
            matched_set = {cid for cid in resolved_cids if cid in hit.entity_ids}

            if hit.source_type == "pubmed" and hit.source_id in pmid_to_pair_edges:
                link_info = pmid_to_pair_edges[hit.source_id]
                matched_set.update(link_info["endpoint_cids"])
                rel_ids = list(link_info["relationship_ids"])
                hit.provenance = {
                    **hit.provenance,
                    "linked_via_relationship_pmid": True,
                    "relationship_id": rel_ids[0],
                    "relationship_ids": rel_ids,
                }
                if "linked_via_relationship_pmid" not in hit.found_by_paths:
                    hit.found_by_paths.append("linked_via_relationship_pmid")

            hit.matched_entities = [cid for cid in resolved_cids if cid in matched_set]

        if len(resolved_cids) >= 2:
            # Rank chunks carrying BOTH IDs first, chunks carrying one next, then rest.
            # Do not hard-drop anything; preserve RRF score within each tier.
            fused_candidates.sort(
                key=lambda h: (-len(h.matched_entities), -h.rrf_score, h.chunk_id)
            )

        # Re-assign rank and cap to top_k
        top_evidence = fused_candidates[: self.config.top_k]
        for idx, hit in enumerate(top_evidence, start=1):
            hit.rank = idx

        return PipelineQueryResult(
            question=question,
            resolved_entities=resolved_entities,
            possible_gene_names_lowercase=possible_lower_genes,
            graph_edges=graph_res.edges,
            graph_columns_used=graph_res.columns_used,
            top_evidence=top_evidence,
            meaning_coverage=self.get_meaning_coverage(),
        )

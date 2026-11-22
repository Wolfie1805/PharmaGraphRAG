"""
Retrieval pipeline orchestrating entity resolution, hybrid search, graph traversal, and RRF fusion.
"""

from typing import Any, Dict, List, Optional, Set

import duckdb
from pydantic import BaseModel, Field

from app.retrieval.config import RetrievalConfig
from app.retrieval.entity_lookup import EntityLookupResult, EntityLookupService
from app.retrieval.fusion import FusedHit, compute_rrf_fusion
from app.retrieval.graph_lookup import GraphEdge, GraphLookupService
from app.retrieval.keyword_search import BM25KeywordIndex
from app.retrieval.meaning_search import MeaningSearchIndex

EVIDENCE_ENTITY_TYPES = frozenset({"gene", "chemical", "variant", "haplotype", "snv"})


def _is_evidence_entity(ent: Any) -> bool:
    """Check if entity is of allowed evidence types (gene, chemical, variant, haplotype, snv)."""
    if getattr(ent, "candidates", None) and ent.candidates:
        t = getattr(ent.candidates[0], "entity_type", "")
        if t and t.lower() in EVIDENCE_ENTITY_TYPES:
            return True
        return False
    if getattr(ent, "candidate_types", None) and ent.candidate_types:
        for ct in ent.candidate_types:
            if ct and ct.lower() in EVIDENCE_ENTITY_TYPES:
                return True
        return False
    if getattr(ent, "entity_type", None):
        return ent.entity_type.lower() in EVIDENCE_ENTITY_TYPES
    cid = str(getattr(ent, "canonical_id", "") or "").lower()
    for prefix in ("gene", "chem", "var", "haplo", "snv"):
        if f":{prefix}:" in cid or cid.startswith(f"pg:{prefix}"):
            return True
    return False


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
        chunks_path = config.resolved_chunks_path
        self.entity_service = EntityLookupService(
            config.processed_dir,
            raw_haplo_dir=config.raw_haplo_dir,
        )
        self.bm25_index = BM25KeywordIndex(chunks_path)
        self.meaning_index = MeaningSearchIndex(
            model_name=config.embedding_model,
            qdrant_path=config.qdrant_path,
            collection_name=config.collection_name,
            chunks_path=chunks_path,
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
        evidence_resolved = [
            e
            for e in resolved_entities
            if getattr(e, "status", "") == "resolved" and _is_evidence_entity(e)
        ]
        resolved_cids = list(
            dict.fromkeys(
                e.canonical_id
                for e in evidence_resolved
                if getattr(e, "canonical_id", None)
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

        # 4b. Structured Entity-Grounded Search (skipped if no resolved entities)
        entity_hits = (
            self.bm25_index.search_by_entities(
                question, resolved_cids, top_k=self.config.entity_path_top_k
            )
            if resolved_cids
            else []
        )

        # 5. Graph edges mapped to source chunks (strictly existing chunks, never stubs)
        graph_chunks: List[Dict[str, Any]] = []
        if graph_res.source_pmids:
            chunks_path = self.config.resolved_chunks_path
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

        # 6. Reciprocal Rank Fusion (k=60), preserving full fused pool for dedup & slot balance
        pool_limit = max(
            50,
            len(keyword_hits) + len(meaning_hits) + len(graph_chunks) + len(entity_hits),
        )
        fused_candidates = compute_rrf_fusion(
            keyword_hits=keyword_hits,
            meaning_hits=meaning_hits,
            graph_chunks=graph_chunks,
            entity_hits=entity_hits,
            k=self.config.rrf_k,
            top_n=pool_limit,
        )

        # 6b. Keep at most one chunk per source_id (the one with best fused rank) before top_k
        seen_source_ids: Set[str] = set()
        deduped_candidates: List[FusedHit] = []
        for hit in fused_candidates:
            if hit.source_id in seen_source_ids:
                continue
            seen_source_ids.add(hit.source_id)
            deduped_candidates.append(hit)
        fused_candidates = deduped_candidates

        # 7. Always resolve entity_ids from the active chunk table by chunk_id
        # (do not rely on potentially stale Qdrant payload entity_ids), then tier-rank.
        for hit in fused_candidates:
            if hit.chunk_id in self._chunk_entity_map:
                hit.entity_ids = list(self._chunk_entity_map[hit.chunk_id])
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

        # 7b. Slot balance before top_k cut:
        # Reserve up to config.curated_slot_reserve slots for configured curated source types
        # carrying ALL resolved entity IDs; cap pubmed at (top_k - reserve) only when >= reserve
        # such curated items exist, otherwise let pubmed fill remaining free slots.
        top_k = self.config.top_k
        curated_types = set(self.config.curated_source_types)
        reserve_target = min(max(0, self.config.curated_slot_reserve), top_k)

        qualifying_curated = (
            [
                h
                for h in fused_candidates
                if h.source_type in curated_types
                and len(h.matched_entities) == len(resolved_cids)
            ]
            if resolved_cids and reserve_target > 0
            else []
        )
        reserved = qualifying_curated[:reserve_target]
        reserved_chunk_ids = {h.chunk_id for h in reserved}
        cap_pubmed_to = (
            (top_k - reserve_target) if len(qualifying_curated) >= reserve_target else None
        )

        selected: List[FusedHit] = list(reserved)
        pubmed_used = sum(1 for h in selected if h.source_type == "pubmed")
        for hit in fused_candidates:
            if len(selected) >= top_k:
                break
            if hit.chunk_id in reserved_chunk_ids:
                continue
            if (
                cap_pubmed_to is not None
                and hit.source_type == "pubmed"
                and pubmed_used >= cap_pubmed_to
            ):
                continue
            selected.append(hit)
            if hit.source_type == "pubmed":
                pubmed_used += 1

        # Preserve deterministic candidate order for final top_evidence
        order_idx = {h.chunk_id: idx for idx, h in enumerate(fused_candidates)}
        selected.sort(key=lambda h: order_idx[h.chunk_id])

        # Re-assign rank
        top_evidence = selected[:top_k]

        # 7c. paper_reserve (config, default 2):
        # In the top 10, linked papers (where source_type == "pubmed",
        # linked_via_relationship_pmid is true, and both endpoints resolve to query pair)
        # take up to that many slots, replacing ONLY the lowest-ranked annotations.
        # Guidelines and drug_labels are NEVER displaced.
        # If no linked papers qualify, top 10 is unchanged.
        # Main claim evidence order: curated first, linked papers after.
        paper_reserve = getattr(self.config, "paper_reserve", 0)
        if paper_reserve > 0 and len(resolved_cids) >= 2:

            def is_qualifying_linked_paper(h: FusedHit) -> bool:
                if h.source_type != "pubmed":
                    return False
                is_linked = (
                    h.provenance.get("linked_via_relationship_pmid") is True
                    or "linked_via_relationship_pmid" in h.found_by_paths
                )
                if not is_linked:
                    return False
                return len(set(h.matched_entities).intersection(resolved_cid_set)) >= 2

            linked_in_top = [h for h in top_evidence if is_qualifying_linked_paper(h)]
            needed = paper_reserve - len(linked_in_top)
            if needed > 0:
                top_chunk_ids = {h.chunk_id for h in top_evidence}
                available_linked = [
                    h
                    for h in fused_candidates
                    if is_qualifying_linked_paper(h) and h.chunk_id not in top_chunk_ids
                ]
                if available_linked:
                    annotation_indices = [
                        idx
                        for idx, h in enumerate(top_evidence)
                        if h.source_type == "annotation"
                    ]
                    displaceable = list(reversed(annotation_indices))
                    num_to_replace = min(needed, len(available_linked), len(displaceable))

                    if num_to_replace > 0:
                        replaced_indices = set(displaceable[:num_to_replace])
                        new_papers = available_linked[:num_to_replace]
                        curated_kept = [
                            h
                            for idx, h in enumerate(top_evidence)
                            if idx not in replaced_indices
                        ]
                        top_evidence = curated_kept + new_papers

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

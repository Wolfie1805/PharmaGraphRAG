"""
Retrieval pipeline orchestrating entity resolution, hybrid search, graph traversal, and RRF fusion.
"""

from typing import Any, Dict, List

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
    graph_edges: List[GraphEdge] = Field(default_factory=list)
    graph_columns_used: List[str] = Field(default_factory=list)
    top_evidence: List[FusedHit] = Field(default_factory=list)


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

    def query(self, question: str) -> PipelineQueryResult:
        """
        Execute full hybrid retrieval pipeline:
        1. Resolve query entities (exact + normalized only)
        2. Graph edge lookup for resolved entities (no multi-hop inference)
        3. BM25 keyword search using biomedical tokenizer
        4. Dense vector meaning search via local Qdrant
        5. Map graph PMIDs to source chunks
        6. Reciprocal Rank Fusion (k=60) returning top 10 with found paths
        """
        # 1. Entity Lookup
        resolved_entities = self.entity_service.extract_and_resolve_entities(question)
        resolved_cids = [
            e.canonical_id for e in resolved_entities if e.status == "resolved" and e.canonical_id
        ]

        # 2. Graph Lookup
        graph_res = self.graph_service.lookup_edges(resolved_cids)

        # 3. Keyword Search
        keyword_hits = self.bm25_index.search(question, top_k=50)

        # 4. Meaning Search
        meaning_hits = self.meaning_index.search(question, top_k=50)

        # 5. Graph edges mapped to source chunks
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
        top_evidence = compute_rrf_fusion(
            keyword_hits=keyword_hits,
            meaning_hits=meaning_hits,
            graph_chunks=graph_chunks,
            k=self.config.rrf_k,
            top_n=self.config.top_k,
        )

        return PipelineQueryResult(
            question=question,
            resolved_entities=resolved_entities,
            graph_edges=graph_res.edges,
            graph_columns_used=graph_res.columns_used,
            top_evidence=top_evidence,
        )

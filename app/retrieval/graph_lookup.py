"""
Graph lookup module: direct edge lookup from relationships.parquet.
Reports and uses only columns that exist. No multi-hop inference.
"""

from pathlib import Path
from typing import List, Set

import duckdb
from pydantic import BaseModel, Field

# Existing columns documented in relationships.parquet
RELATIONSHIPS_COLUMNS = [
    "relationship_id",
    "entity1_id",
    "entity1_name",
    "entity1_type",
    "entity1_canonical_id",
    "entity2_id",
    "entity2_name",
    "entity2_type",
    "entity2_canonical_id",
    "association",
    "pmids",
    "is_dangling",
    "raw_file_sha256",
]


class GraphEdge(BaseModel):
    """Knowledge graph edge from relationships.parquet."""

    relationship_id: str
    entity1_canonical_id: str
    entity1_name: str
    entity1_type: str
    entity2_canonical_id: str
    entity2_name: str
    entity2_type: str
    association: str
    pmids: List[str] = Field(default_factory=list, description="Explicit PMIDs supporting edge")


class GraphLookupResult(BaseModel):
    """Result of graph lookup over resolved entities."""

    edges: List[GraphEdge] = Field(default_factory=list)
    columns_used: List[str] = Field(default_factory=list)
    source_pmids: List[str] = Field(default_factory=list)


class GraphLookupService:
    """Queries relationships.parquet directly without multi-hop inference."""

    def __init__(self, processed_dir: Path = Path("data/processed")):
        self.relationships_path = processed_dir / "relationships.parquet"
        self._con = duckdb.connect(":memory:")

    def lookup_edges(self, resolved_canonical_ids: List[str]) -> GraphLookupResult:
        """
        Lookup edges connecting the resolved entities.
        - If >= 2 entities: returns edges connecting pairwise between them.
        - If 1 entity: returns direct 1-hop edges for that entity.
        - If 0 entities: returns empty list.
        """
        if not resolved_canonical_ids:
            return GraphLookupResult(
                edges=[],
                columns_used=RELATIONSHIPS_COLUMNS,
                source_pmids=[],
            )

        unique_ids = list(dict.fromkeys(resolved_canonical_ids))

        if len(unique_ids) >= 2:
            # Pairwise direct edges between resolved entities
            placeholders = ", ".join(["?"] * len(unique_ids))
            sql = f"""
                SELECT relationship_id, entity1_canonical_id, entity1_name, entity1_type,
                       entity2_canonical_id, entity2_name, entity2_type,
                       association, pmids
                FROM '{self.relationships_path.as_posix()}'
                WHERE entity1_canonical_id IN ({placeholders})
                  AND entity2_canonical_id IN ({placeholders})
            """
            rows = self._con.execute(sql, unique_ids + unique_ids).fetchall()
        else:
            # 1-hop edges for the single entity
            sql = f"""
                SELECT relationship_id, entity1_canonical_id, entity1_name, entity1_type,
                       entity2_canonical_id, entity2_name, entity2_type,
                       association, pmids
                FROM '{self.relationships_path.as_posix()}'
                WHERE entity1_canonical_id = ?
                   OR entity2_canonical_id = ?
                LIMIT 50
            """
            rows = self._con.execute(sql, [unique_ids[0], unique_ids[0]]).fetchall()

        edges: List[GraphEdge] = []
        all_pmids: Set[str] = set()

        for r in rows:
            rel_id, e1_cid, e1_n, e1_t, e2_cid, e2_n, e2_t, assoc, pmids_raw = r
            if isinstance(pmids_raw, list):
                pmid_list = [str(p).strip() for p in pmids_raw if str(p).strip()]
            elif isinstance(pmids_raw, str):
                pmid_list = [p.strip() for p in pmids_raw.split(",") if p.strip()]
            else:
                pmid_list = []
            all_pmids.update(pmid_list)
            edges.append(
                GraphEdge(
                    relationship_id=rel_id,
                    entity1_canonical_id=e1_cid,
                    entity1_name=e1_n or "",
                    entity1_type=e1_t or "",
                    entity2_canonical_id=e2_cid,
                    entity2_name=e2_n or "",
                    entity2_type=e2_t or "",
                    association=assoc or "",
                    pmids=pmid_list,
                )
            )

        return GraphLookupResult(
            edges=edges,
            columns_used=RELATIONSHIPS_COLUMNS,
            source_pmids=sorted(list(all_pmids)),
        )

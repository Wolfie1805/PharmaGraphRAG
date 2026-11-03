"""
Meaning search module: dense embedding and vector search using local Qdrant on disk.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import duckdb
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer


class MeaningHit(BaseModel):
    """Dense vector search hit."""

    chunk_id: str
    source_type: str
    source_id: str
    title: str
    content: str
    date: str
    date_precision: str
    entity_ids: List[str] = Field(default_factory=list)
    dense_score: float
    rank: int


class MeaningSearchIndex:
    """Local on-disk Qdrant vector index over data/processed/chunks.parquet."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        qdrant_path: Path = Path("data/processed/qdrant_db"),
        collection_name: str = "pharmagraph_chunks",
        chunks_path: Path = Path("data/processed/chunks.parquet"),
    ):
        self.model_name = model_name
        self.qdrant_path = qdrant_path
        self.collection_name = collection_name
        self.chunks_path = chunks_path
        self.manifest_path = qdrant_path / "qdrant_manifest.json"

        self.qdrant_path.mkdir(parents=True, exist_ok=True)
        self.client = QdrantClient(path=str(self.qdrant_path))
        self.encoder = SentenceTransformer(self.model_name)
        self.vector_dim = self.encoder.get_sentence_embedding_dimension() or 384

    def build_index(self, force_rebuild: bool = False, batch_size: int = 64) -> int:
        """
        Embed all chunks and populate local Qdrant collection.
        Saves metadata manifest on completion.
        """
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if exists and not force_rebuild:
            count = self.client.count(collection_name=self.collection_name).count
            if count > 0:
                return count

        # Create or recreate collection
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=self.vector_dim, distance=Distance.COSINE),
        )

        con = duckdb.connect(":memory:")
        sql = f"""
            SELECT chunk_id, source_type, source_id, title, content,
                   date, date_precision, entity_ids
            FROM '{self.chunks_path.as_posix()}'
        """
        rows = con.execute(sql).fetchall()

        total_chunks = len(rows)
        points: List[PointStruct] = []

        for start_idx in range(0, total_chunks, batch_size):
            batch_rows = rows[start_idx : start_idx + batch_size]
            texts_to_embed = [
                f"{r[3]} {r[4]}".strip() for r in batch_rows
            ]
            embeddings = self.encoder.encode(
                texts_to_embed,
                batch_size=batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
            )

            for offset, r in enumerate(batch_rows):
                point_id = start_idx + offset
                chunk_id, st, sid, title, content, dt, dp, eids = r
                payload: Dict[str, Any] = {
                    "chunk_id": chunk_id,
                    "source_type": st,
                    "source_id": sid,
                    "title": title or "",
                    "content": content or "",
                    "date": dt or "unknown",
                    "date_precision": dp or "unknown",
                    "entity_ids": list(eids) if eids else [],
                }
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=embeddings[offset].tolist(),
                        payload=payload,
                    )
                )

            # Upsert batch
            if len(points) >= 500 or (start_idx + batch_size) >= total_chunks:
                self.client.upsert(collection_name=self.collection_name, points=points)
                points = []

        final_count = self.client.count(collection_name=self.collection_name).count

        # Write manifest
        manifest_data = {
            "model_name": self.model_name,
            "vector_dimension": self.vector_dim,
            "total_points": final_count,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "collection_name": self.collection_name,
        }
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        return final_count

    def close(self):
        """Explicitly close QdrantClient."""
        if hasattr(self, "client") and self.client is not None:
            try:
                self.client.close()
            except Exception:
                pass

    def search(self, query: str, top_k: int = 50) -> List[MeaningHit]:
        """Search chunks with dense vector embeddings."""
        query_vector = self.encoder.encode(
            [query], normalize_embeddings=True
        )[0].tolist()

        if hasattr(self.client, "query_points"):
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
            )
            search_result = response.points
        else:
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
            )

        hits: List[MeaningHit] = []
        for rank, res in enumerate(search_result, start=1):
            payload = res.payload or {}
            hits.append(
                MeaningHit(
                    chunk_id=str(payload.get("chunk_id", "")),
                    source_type=str(payload.get("source_type", "")),
                    source_id=str(payload.get("source_id", "")),
                    title=str(payload.get("title", "")),
                    content=str(payload.get("content", "")),
                    date=str(payload.get("date", "unknown")),
                    date_precision=str(payload.get("date_precision", "unknown")),
                    entity_ids=list(payload.get("entity_ids", [])),
                    dense_score=float(res.score),
                    rank=rank,
                )
            )
        return hits

"""
Keyword search module: BM25 index over processed chunks with biomedical tokenizer.
"""

from pathlib import Path
from typing import Any, Dict, List

import duckdb
from pydantic import BaseModel, Field
from rank_bm25 import BM25Okapi

from app.retrieval.tokenizer import tokenize_biomedical


class KeywordHit(BaseModel):
    """BM25 search result hit."""

    chunk_id: str
    source_type: str
    source_id: str
    title: str
    content: str
    date: str
    date_precision: str
    entity_ids: List[str] = Field(default_factory=list)
    bm25_score: float
    rank: int


class BM25KeywordIndex:
    """In-memory BM25 index over data/processed/chunks.parquet."""

    def __init__(self, chunks_path: Path = Path("data/processed/chunks.parquet")):
        self.chunks_path = chunks_path
        self.chunk_records: List[Dict[str, Any]] = []
        self.corpus_tokens: List[List[str]] = []
        self.bm25: BM25Okapi = None  # type: ignore
        self._build_index()

    def _build_index(self) -> None:
        """Load chunks and build BM25 index."""
        if not self.chunks_path.exists():
            raise FileNotFoundError(f"Chunks table not found at {self.chunks_path}")

        con = duckdb.connect(":memory:")
        sql = f"""
            SELECT chunk_id, source_type, source_id, title, content,
                   date, date_precision, entity_ids
            FROM '{self.chunks_path.as_posix()}'
        """
        rows = con.execute(sql).fetchall()
        for r in rows:
            chunk_id, st, sid, title, content, dt, dp, eids = r
            rec = {
                "chunk_id": chunk_id,
                "source_type": st,
                "source_id": sid,
                "title": title or "",
                "content": content or "",
                "date": dt or "unknown",
                "date_precision": dp or "unknown",
                "entity_ids": list(eids) if eids else [],
            }
            self.chunk_records.append(rec)
            # Tokenize title and content together
            combined_text = f"{rec['title']} {rec['content']}"
            tokens = tokenize_biomedical(combined_text)
            self.corpus_tokens.append(tokens)

        self.bm25 = BM25Okapi(self.corpus_tokens)

    def search(self, query: str, top_k: int = 50) -> List[KeywordHit]:
        """Search chunks with BM25 using biomedical tokenizer."""
        query_tokens = tokenize_biomedical(query)
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)

        # Get top indices with score > 0
        scored_indices = [
            (idx, score) for idx, score in enumerate(scores) if score > 0.0
        ]
        scored_indices.sort(key=lambda x: x[1], reverse=True)
        top_indices = scored_indices[:top_k]

        hits: List[KeywordHit] = []
        for rank, (idx, score) in enumerate(top_indices, start=1):
            chunk = self.chunk_records[idx]
            hits.append(
                KeywordHit(
                    chunk_id=chunk["chunk_id"],
                    source_type=chunk["source_type"],
                    source_id=chunk["source_id"],
                    title=chunk["title"],
                    content=chunk["content"],
                    date=chunk["date"],
                    date_precision=chunk["date_precision"],
                    entity_ids=chunk["entity_ids"],
                    bm25_score=float(score),
                    rank=rank,
                )
            )
        return hits

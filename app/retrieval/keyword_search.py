"""
Keyword search module: BM25 index over processed chunks with biomedical tokenizer.
"""

from pathlib import Path
from typing import Any, Dict, List

import duckdb
from pydantic import BaseModel, Field
from rank_bm25 import BM25Okapi

from app.retrieval.tokenizer import tokenize_biomedical

# English stopwords plus query scaffolding aligned with EntityLookupService
BM25_STOPWORDS = frozenset(
    {
        "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
        "any", "are", "as", "at", "be", "because", "been", "before", "being", "below",
        "between", "both", "but", "by", "can", "could", "did", "do", "does", "doing",
        "down", "during", "each", "few", "for", "from", "further", "had", "has", "have",
        "having", "he", "her", "here", "hers", "herself", "him", "himself", "his", "how",
        "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me", "might",
        "more", "most", "must", "my", "myself", "no", "nor", "not", "now", "of", "off",
        "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out",
        "over", "own", "relationship", "same", "she", "should", "so", "some", "such",
        "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there",
        "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
        "very", "was", "we", "were", "what", "when", "where", "which", "while", "who",
        "whom", "why", "will", "with", "would", "you", "your", "yours", "yourself",
        "yourselves",
    }
)


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
            # Tokenize title and content together, excluding common stopwords
            combined_text = f"{rec['title']} {rec['content']}"
            tokens = [
                t for t in tokenize_biomedical(combined_text) if t not in BM25_STOPWORDS
            ]
            self.corpus_tokens.append(tokens)

        self.bm25 = BM25Okapi(self.corpus_tokens) if self.corpus_tokens else None

    def search(self, query: str, top_k: int = 50) -> List[KeywordHit]:
        """Search chunks with BM25 using biomedical tokenizer."""
        query_tokens = [
            t for t in tokenize_biomedical(query) if t not in BM25_STOPWORDS
        ]
        if not query_tokens or self.bm25 is None:
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

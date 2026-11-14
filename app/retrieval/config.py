"""
Configuration module for Demo D1 retrieval core.
"""

import os
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field


class RetrievalConfig(BaseModel):
    """Configuration for biomedical retrieval pipeline."""

    embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5",
        description="Default sentence-transformers embedding model name or path.",
    )
    qdrant_path: Path = Field(
        default_factory=lambda: Path(
            os.getenv("PHARMAGRAPH_QDRANT_PATH", "data/processed/qdrant_db_full")
        ),
        description="Local disk directory for embedded Qdrant vector database.",
    )
    chunks_path: Path = Field(
        default_factory=lambda: Path(
            os.getenv("PHARMAGRAPH_CHUNKS_PATH", "data/processed/chunks_v2.parquet")
        ),
        description="Path to chunks Parquet table.",
    )
    collection_name: str = Field(
        default="pharmagraph_chunks",
        description="Name of the Qdrant chunk collection.",
    )
    rrf_k: int = Field(
        default=60,
        description="Reciprocal Rank Fusion smoothing constant k.",
    )
    top_k: int = Field(
        default=10,
        description="Top K results to return from fusion.",
    )
    entity_path_top_k: int = Field(
        default=50,
        description="Top K candidates from the structured entity-grounded path.",
    )
    curated_slot_reserve: int = Field(
        default=5,
        description="Max top_k slots reserved for curated sources carrying all resolved entities.",
    )
    curated_source_types: List[str] = Field(
        default_factory=lambda: ["guideline", "annotation", "drug_label"],
        description="Curated source types eligible for slot reservation before top_k cut.",
    )
    processed_dir: Path = Field(
        default=Path("data/processed"),
        description="Directory containing normalized Parquet tables.",
    )
    raw_clinpgx_dir: Path = Field(
        default=Path("data/raw/clinpgx/20261030_79ff97e7"),
        description="Raw ClinPGx manifest directory containing archives.",
    )
    raw_haplo_dir: Path = Field(
        default=Path("data/raw/clinpgx/20261031_d2a604a2"),
        description="Raw haplotype manifest directory.",
    )

    @property
    def resolved_chunks_path(self) -> Path:
        """Resolve chunks Parquet path respecting explicit overrides, env var, or processed_dir."""
        if "chunks_path" in self.model_fields_set or os.getenv("PHARMAGRAPH_CHUNKS_PATH"):
            return self.chunks_path
        if self.processed_dir != Path("data/processed"):
            return self.processed_dir / "chunks.parquet"
        return self.chunks_path

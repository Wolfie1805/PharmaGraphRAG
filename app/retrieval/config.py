"""
Configuration module for Demo D1 retrieval core.
"""

import os
from pathlib import Path

from pydantic import BaseModel, Field


class RetrievalConfig(BaseModel):
    """Configuration for biomedical retrieval pipeline."""

    embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5",
        description="Default sentence-transformers embedding model name or path.",
    )
    qdrant_path: Path = Field(
        default_factory=lambda: Path(
            os.getenv("PHARMAGRAPH_QDRANT_PATH", "data/processed/qdrant_db")
        ),
        description="Local disk directory for embedded Qdrant vector database.",
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

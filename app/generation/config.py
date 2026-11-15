"""
Configuration for Phase D2 generation layer and answer modes.
Supports:
1. extractive (DEFAULT): no model, no network.
2. ollama (OPTIONAL, off by default): local model via http://localhost:11434 using httpx.
3. mock: for tests only.
"""

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables from .env if present
_env_path = Path(".env")
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path, override=False)

DEFAULT_DISCLAIMER = (
    "PharmaGraph is an experimental research system for pharmacogenomics intelligence "
    "and does NOT provide medical advice, clinical diagnosis, or dosing recommendations. "
    "Always consult a licensed physician, clinical geneticist, or pharmacist for medical decisions."
)

AnswerMode = Literal["extractive", "ollama", "mock"]


class GenerationConfig(BaseModel):
    """Runtime configuration for generation, checks, and API."""

    llm_mode: AnswerMode = Field(
        default_factory=lambda: os.getenv("LLM_MODE", "extractive").lower()  # type: ignore
    )
    llm_provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "local"))
    llm_base_url: str = Field(
        default_factory=lambda: os.getenv("LLM_BASE_URL", "http://localhost:11434")
    )
    llm_model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "llama3"))
    llm_timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("LLM_TIMEOUT_SECONDS", "180.0"))
    )
    llm_allow_non_localhost: bool = Field(
        default_factory=lambda: os.getenv("LLM_ALLOW_NON_LOCALHOST", "false").lower() == "true"
    )

    max_extractive_claims: int = 8
    max_related_claims: int = 4
    max_excerpt_chars: int = 300
    seed: int = 42
    temperature: float = 0.0

    min_evidence_items: int = 3
    min_top_score: float = 0.015
    request_timeout_seconds: float = 30.0
    max_entity_hints: int = 4
    disclaimer_text: str = DEFAULT_DISCLAIMER

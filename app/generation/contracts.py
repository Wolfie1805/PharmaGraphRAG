"""
Data contracts for Phase D2 generation layer and API responses.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """Structured evidence item included in the bundle."""

    source_id: str
    source_type: str
    title: str
    date: Optional[str] = "unspecified"
    date_precision: Optional[str] = "unspecified"
    chunk_text: str
    entities: List[str] = Field(default_factory=list)
    matched_entities: List[str] = Field(default_factory=list)
    retrieval_paths: List[str] = Field(default_factory=list)
    score: float = 0.0
    graph_edges: List[Dict[str, Any]] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)


class EvidenceBundle(BaseModel):
    """Complete bundle of evidence items passed to the generation layer."""

    query: str
    resolved_entity_ids: List[str] = Field(default_factory=list)
    items: List[EvidenceItem] = Field(default_factory=list)
    total_items: int = 0
    has_sufficient_evidence: bool = True
    conflicts_detected: bool = False
    conflict_details: Optional[str] = None


class Claim(BaseModel):
    """An individual assertion with its supporting source IDs."""

    text: str
    source_ids: List[str] = Field(default_factory=list)


class LLMOutput(BaseModel):
    """Raw structured output produced by the LLM or extractive builder."""

    answer: str
    claims: List[Claim] = Field(default_factory=list)
    related_claims: List[Claim] = Field(default_factory=list)
    conflicts: str = "None noted."
    limitations: str = ""
    answer_mode: str = "extractive"


class AskRequest(BaseModel):
    """Incoming query request for the API."""

    question: str = Field(..., max_length=10000, description="Biomedical question")


class AskResponse(BaseModel):
    """Final API response for POST /api/ask."""

    question: str
    answer: str
    claims: List[Claim] = Field(default_factory=list)
    related_claims: List[Claim] = Field(default_factory=list)
    evidence_bundle: EvidenceBundle
    resolved_entities: List[Dict[str, Any]] = Field(default_factory=list)
    flags: List[str] = Field(default_factory=list)
    removed_claims_count: int = 0
    disclaimer_text: str
    answer_mode: str = "extractive"
    llm_calls: int = 0
    network_calls: int = 0
    builder_calls: int = 0

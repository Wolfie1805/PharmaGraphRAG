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
    entity_hints: Optional[List[str]] = Field(
        default=None,
        description="Optional canonical entity IDs to resolve without ambiguity.",
    )
    overview_offset: int = Field(
        default=0, ge=0, description="Pagination offset for overview rows."
    )
    overview_limit: int = Field(
        default=20, ge=1, le=100, description="Pagination limit for overview rows."
    )


class OverviewRow(BaseModel):
    """Structured gene-chemical relationship overview row."""

    target_id: str
    target_name: str
    target_type: str
    other_id: str
    other_name: str
    other_type: str
    chemical_id: str
    chemical_name: str
    gene_id: str
    gene_name: str
    association: str
    annotation_count: int = 0
    drug_label_count: int = 0
    guideline_count: int = 0
    curated_count: int = 0
    linked_papers_count: int = 0


class OverviewData(BaseModel):
    """Complete overview table response with pagination metadata."""

    total_count: int = 0
    offset: int = 0
    limit: int = 20
    rows: List[OverviewRow] = Field(default_factory=list)


class VariantFindingItem(BaseModel):
    """Structured variant-level clinical finding with raw columns mapped."""

    source_id: str
    title: str
    sentence: str
    significance: Optional[str] = None
    phenotype_category: Optional[str] = None
    direction_of_effect: Optional[str] = None
    population_types: Optional[str] = None
    pmid: Optional[str] = None
    source_columns: Dict[str, str] = Field(default_factory=dict)


class VariantFindingGroup(BaseModel):
    """Findings grouped by variant or allele tag."""

    variant_tag: str
    display_name: str
    canonical_id: Optional[str] = None
    findings: List[VariantFindingItem] = Field(default_factory=list)


class DetailSections(BaseModel):
    """Evidence grouped into explicit sections for detail query modes."""

    guidelines: List[EvidenceItem] = Field(default_factory=list)
    drug_labels: List[EvidenceItem] = Field(default_factory=list)
    variant_findings: List[VariantFindingGroup] = Field(default_factory=list)
    linked_papers: List[EvidenceItem] = Field(default_factory=list)
    all_linked_papers: List[EvidenceItem] = Field(default_factory=list)
    recorded_relationships: List[EvidenceItem] = Field(default_factory=list)
    guidelines_label: Optional[str] = None
    drug_labels_label: Optional[str] = None


class SuggestedNextItem(BaseModel):
    """Deterministic follow-up query suggestion derived from graph edges."""

    label: str
    entity_ids: List[str] = Field(default_factory=list)


class PromptTemplateItem(BaseModel):
    """Supported query structure template."""

    name: str
    shape: str
    template: str
    example: str
    description: str


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
    meaning_coverage: Dict[str, Any] = Field(default_factory=dict)
    llm_calls: int = 0
    network_calls: int = 0
    builder_calls: int = 0
    query_mode: str = "unrecognized"
    overview: Optional[OverviewData] = None
    sections: Optional[DetailSections] = None
    suggested_next: List[SuggestedNextItem] = Field(default_factory=list)
    prompt_templates: List[PromptTemplateItem] = Field(default_factory=list)

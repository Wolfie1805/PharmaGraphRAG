"""
Pydantic contracts and data models for Phase 2 data normalization.
Strict typing, explicit field constraints, provenance tracking, and license metadata.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class SourceProvenance(BaseModel):
    """Immutable provenance record tracking every processed entity back to raw archives."""

    model_config = ConfigDict(frozen=True)

    source_name: str = Field(..., description="Data source name ('ClinPGx', 'CPIC', 'PubMed')")
    license_text: str = Field(..., description="Governing license terms text")
    license_check_date: str = Field(
        ..., description="UTC date when license was verified (YYYY-MM-DD)"
    )
    raw_file_path: str = Field(..., description="Relative path to raw archive or XML file")
    raw_file_sha256: str = Field(..., description="SHA-256 hash of the raw archive")
    manifest_run_id: str = Field(..., description="Phase 1 manifest run ID")
    record_index: int = Field(..., ge=1, description="1-based line or element index in source")


class EntityRecord(BaseModel):
    """Unified canonical entity representation."""

    model_config = ConfigDict(frozen=True)

    canonical_id: str = Field(..., description="Stable internal identifier (e.g. pg:chem:000001)")
    entity_type: Literal["gene", "chemical", "variant", "haplotype", "snv", "phenotype", "cnv"] = (
        Field(..., description="Entity domain type")
    )
    primary_source_id: str = Field(
        ..., description="Source-provided primary identifier (PA..., rs...)"
    )
    display_name: str = Field(..., description="Verbatim casing display name from source")
    normalized_name: str = Field(..., description="NFKC, case-folded search string")
    is_drug: bool = Field(
        default=False, description="True if chemical is approved/categorized as drug"
    )
    gene_symbol: Optional[str] = Field(
        default=None, description="Associated gene symbol for alleles/genes"
    )
    defined_by: Literal["primary_definition", "relationships_only"] = Field(
        default="primary_definition", description="Origin of entity definition"
    )
    is_ambiguous: bool = Field(
        default=False, description="True if surface form maps to multiple entities"
    )
    is_artifact: bool = Field(
        default=False, description="True if name/identifier has source corruption"
    )
    provenance: SourceProvenance


class CrossReferenceRecord(BaseModel):
    """External authority cross-reference identifier."""

    model_config = ConfigDict(frozen=True)

    canonical_id: str = Field(..., description="Reference to EntityRecord.canonical_id")
    namespace: str = Field(
        ..., description="Authority ('NCBI_GENE', 'ENSEMBL', 'HGNC', 'DRUGBANK', etc.)"
    )
    external_id: str = Field(..., description="External accession or identifier string")
    provenance: SourceProvenance


class SynonymRecord(BaseModel):
    """Alternative surface form, trade name, or alias."""

    model_config = ConfigDict(frozen=True)

    canonical_id: str = Field(..., description="Reference to EntityRecord.canonical_id")
    synonym_text: str = Field(..., description="Verbatim alias text from source")
    normalized_synonym: str = Field(..., description="NFKC, case-folded search string")
    synonym_type: str = Field(..., description="Category ('trade_name', 'alternate_name', etc.)")
    is_ambiguous: bool = Field(
        default=False, description="True if surface form maps to multiple accessions"
    )
    is_artifact: bool = Field(default=False, description="True if alias is malformed in source")
    is_split_ambiguous: bool = Field(
        default=False, description="True if commas occurred inside parens"
    )
    provenance: SourceProvenance


class RelationshipRecord(BaseModel):
    """Inter-entity clinical/pharmacogenomic association."""

    model_config = ConfigDict(frozen=True)

    relationship_id: str = Field(..., description="Deterministic hash ID rel:<md5>")
    entity1_id: str = Field(..., description="Raw source ID for entity 1")
    entity1_name: str = Field(..., description="Raw source name for entity 1")
    entity1_type: str = Field(..., description="Source-stated type for entity 1")
    entity1_canonical_id: Optional[str] = Field(
        default=None, description="Canonical ID if resolved"
    )
    entity2_id: str = Field(..., description="Raw source ID for entity 2")
    entity2_name: str = Field(..., description="Raw source name for entity 2")
    entity2_type: str = Field(..., description="Source-stated type for entity 2")
    entity2_canonical_id: Optional[str] = Field(
        default=None, description="Canonical ID if resolved"
    )
    association: str = Field(..., description="Association term ('associated', 'not associated')")
    pmids: List[str] = Field(default_factory=list, description="Supporting PubMed IDs")
    is_dangling: bool = Field(
        default=False, description="True if either endpoint is relationships_only"
    )
    provenance: SourceProvenance


class PublicationRecord(BaseModel):
    """PubMed bibliographic record with structured abstract and MeSH metadata."""

    model_config = ConfigDict(frozen=True)

    pmid: str = Field(..., pattern=r"^\d+$", description="Digits-only PubMed ID")
    record_type: Literal["PubmedArticle", "PubmedBookArticle"] = Field(
        ..., description="Record XML schema type"
    )
    title: str = Field(..., description="Normalized article or book chapter title")
    journal_or_book: str = Field(..., description="Journal title or Bookshelf title")
    pubdate_iso: str = Field(..., description="Standardized ISO date (YYYY, YYYY-MM, YYYY-MM-DD)")
    date_precision: Literal["year", "month", "day"] = Field(
        ..., description="Precision level of pubdate_iso"
    )
    pubdate_raw_year: Optional[str] = None
    pubdate_raw_month: Optional[str] = None
    pubdate_raw_day: Optional[str] = None
    pubdate_raw_medline: Optional[str] = None
    doi: Optional[str] = None
    book_accession: Optional[str] = None
    abstract_text: str = Field(..., description="Full concatenated abstract text")
    abstract_structured: bool = Field(
        default=False, description="True if abstract contains labeled sections"
    )
    abstract_sections: Optional[str] = Field(
        default=None, description="JSON string of structured sections"
    )
    mesh_terms: List[str] = Field(default_factory=list, description="MeSH Descriptor names")
    provenance: SourceProvenance

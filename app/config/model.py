"""PharmaGraph Phase 1 Configuration Models & Validation.

Validated with Pydantic; fails fast on invalid values.
"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GeneDrugPair(BaseModel):
    id: str = Field(min_length=1, description="Unique identifier for the pair")
    gene: str = Field(min_length=1, description="Official gene symbol (e.g. CYP2C19)")
    drug: str = Field(min_length=1, description="Drug name (e.g. clopidogrel)")

    @field_validator("id", "gene", "drug")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("String field cannot be empty or whitespace only")
        return s


class DateRange(BaseModel):
    mindate: Optional[str] = None
    maxdate: Optional[str] = None


class RetrySettings(BaseModel):
    max_retries: int = Field(default=5, ge=1, le=10)
    backoff_factor: float = Field(default=1.5, ge=0.1, le=10.0)
    status_forcelist: list[int] = Field(default_factory=lambda: [429, 500, 502, 503, 504])
    retry_on_rate_limit_body: bool = True


class PubMedConfig(BaseModel):
    base_url: str = Field(min_length=1)
    db: str = Field(default="pubmed")
    require_abstract: bool = True
    abstract_filter: str = "hasabstract[text]"
    date_range: DateRange = Field(default_factory=DateRange)
    max_records_per_pair: int = Field(default=500, ge=1)
    efetch_batch_size: int = Field(default=200, ge=1, le=500)
    rate_limit_rps_default: float = Field(default=2.0, gt=0.0, le=3.0)
    rate_limit_rps_with_key: float = Field(default=8.0, gt=0.0, le=10.0)
    retry: RetrySettings = Field(default_factory=RetrySettings)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        s = v.strip()
        if not (s.startswith("http://") or s.startswith("https://")):
            raise ValueError("base_url must start with http:// or https://")
        return s


class ClinPGxConfig(BaseModel):
    base_url: str = Field(min_length=1)
    catalog_endpoint: str = Field(min_length=1)
    download_endpoint_template: str = Field(min_length=1)
    request_delay_seconds: float = Field(default=0.5, ge=0.0, le=10.0)
    selected_files: list[str] = Field(min_length=1)

    @field_validator("selected_files")
    @classmethod
    def validate_selected_files(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("selected_files list cannot be empty")
        for item in v:
            if not item.endswith((".zip", ".tsv", ".json")):
                raise ValueError(f"Unexpected file extension in selected file: {item}")
        return v


class StorageConfig(BaseModel):
    raw_dir: Path = Field(default=Path("data/raw"))
    manifests_dir: Path = Field(default=Path("data/manifests"))


class AcquisitionConfig(BaseModel):
    version: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    gene_drug_pairs: list[GeneDrugPair] = Field(min_length=1)
    pubmed: PubMedConfig
    clinpgx: ClinPGxConfig
    storage: StorageConfig = Field(default_factory=StorageConfig)


class NCBISettings(BaseSettings):
    """Loads NCBI credentials from environment variables / .env.

    Secrets are never hardcoded and never committed.
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ncbi_api_key: Optional[str] = Field(default=None, alias="NCBI_API_KEY")
    ncbi_email: Optional[str] = Field(default=None, alias="NCBI_EMAIL")
    ncbi_tool: str = Field(default="PharmaGraph", alias="NCBI_TOOL")

    def get_redacted_api_key(self) -> str:
        if not self.ncbi_api_key:
            return "none"
        return "***REDACTED***"


def load_acquisition_config(config_path: Path | str) -> AcquisitionConfig:
    """Load and validate acquisition YAML configuration."""
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path.resolve()}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML content in {path.resolve()}, expected mapping")
    return AcquisitionConfig.model_validate(data)


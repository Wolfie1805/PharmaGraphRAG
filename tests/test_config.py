"""Tests for Phase 1 configuration loading and validation."""

import pytest
from pydantic import ValidationError

from app.config.model import AcquisitionConfig, load_acquisition_config


def test_load_default_acquisition_config():
    config = load_acquisition_config("configs/acquisition.yaml")
    assert config.version == "1.0.0"
    assert config.domain == "pharmacogenomics_cardiovascular"
    assert len(config.gene_drug_pairs) == 4
    assert config.pubmed.efetch_batch_size == 200
    assert config.pubmed.rate_limit_rps_default == 2.0
    assert len(config.clinpgx.selected_files) == 10


def test_config_fails_on_empty_gene_drug():
    config_dict = {
        "version": "1.0.0",
        "domain": "test",
        "gene_drug_pairs": [{"id": "pair1", "gene": "   ", "drug": "warfarin"}],
        "pubmed": {
            "base_url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
            "max_records_per_pair": 100,
            "efetch_batch_size": 50,
            "rate_limit_rps_default": 2.0,
            "rate_limit_rps_with_key": 8.0,
        },
        "clinpgx": {
            "base_url": "https://api.clinpgx.org/v1",
            "catalog_endpoint": "/data/file/data/?view=min",
            "download_endpoint_template": "/download/{file_name}",
            "selected_files": ["genes.zip"],
        },
    }
    with pytest.raises(ValidationError):
        AcquisitionConfig.model_validate(config_dict)


def test_config_fails_on_unsafe_rate_limits():
    # NCBI ceiling without key is 3.0; config model enforces le=3.0
    config_dict = {
        "version": "1.0.0",
        "domain": "test",
        "gene_drug_pairs": [{"id": "pair1", "gene": "CYP2C19", "drug": "clopidogrel"}],
        "pubmed": {
            "base_url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
            "rate_limit_rps_default": 5.0,  # Invalid: > 3.0
        },
        "clinpgx": {
            "base_url": "https://api.clinpgx.org/v1",
            "catalog_endpoint": "/data/file/data/?view=min",
            "download_endpoint_template": "/download/{file_name}",
            "selected_files": ["genes.zip"],
        },
    }
    with pytest.raises(ValidationError):
        AcquisitionConfig.model_validate(config_dict)


def test_config_fails_on_nonexistent_file(tmp_path):
    non_existent = tmp_path / "does_not_exist.yaml"
    with pytest.raises(FileNotFoundError):
        load_acquisition_config(non_existent)


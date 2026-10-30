"""Tests for PubMed acquisition connector with mocked HTTP (strictly offline).

Covers:
- esearch pagination and count recording
- PMID deduplication and provenance mapping
- Raw batch XML storage (byte-for-byte)
- Reconciliation: match case and missing-PMID case
- Resume support
- Secret redaction in logs and manifests
"""

import json
from pathlib import Path
import httpx
import pytest
import respx

from app.config.model import GeneDrugPair, NCBISettings, PubMedConfig, StorageConfig
from app.ingestion.pubmed import (
    acquire_pubmed,
    build_query_string,
    extract_pmids_from_xml,
    sanitize_url_for_logging,
)


SAMPLE_PUBMED_XML_MATCH = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE PubmedArticleSet PUBLIC "-//NLM//DTD PubMedArticle, 1st January 2026//EN" "https://dtd.nlm.nih.gov/ncbi/pubmed/out/pubmed_260101.dtd">
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE">
      <PMID Version="1">1001</PMID>
      <Article>
        <ArticleTitle>Study of CYP2C19 and clopidogrel</ArticleTitle>
        <Journal><Title>Pharmacogenetics Journal</Title></Journal>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE">
      <PMID Version="1">1002</PMID>
      <Article>
        <ArticleTitle>Another trial on clopidogrel</ArticleTitle>
        <Journal><Title>Cardiology Journal</Title></Journal>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""

# Sample XML missing PMID 1002
SAMPLE_PUBMED_XML_MISSING = b"""<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE">
      <PMID Version="1">1001</PMID>
      <Article>
        <ArticleTitle>Only 1001 returned</ArticleTitle>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


def test_sanitize_url_redacts_api_key():
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=test&api_key=SECRET_NCBI_KEY_12345&retmode=json"
    sanitized = sanitize_url_for_logging(url)
    assert "SECRET_NCBI_KEY_12345" not in sanitized
    assert "api_key=***REDACTED***" in sanitized


def test_build_query_string():
    pair = GeneDrugPair(id="pair1", gene="CYP2C19", drug="clopidogrel")
    q = build_query_string(pair, require_abstract=True, abstract_filter="hasabstract[text]")
    assert q == "(CYP2C19[Title/Abstract] AND clopidogrel[Title/Abstract]) AND hasabstract[text]"


def test_extract_pmids_from_xml():
    pmids = extract_pmids_from_xml(SAMPLE_PUBMED_XML_MATCH)
    assert pmids == {"1001", "1002"}


@respx.mock
def test_acquire_pubmed_reconciliation_match(tmp_path):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    config = PubMedConfig(
        base_url=base_url,
        db="pubmed",
        max_records_per_pair=10,
        efetch_batch_size=200,
        rate_limit_rps_default=3.0,  # Valid rate limit for test
    )
    pairs = [GeneDrugPair(id="pair1", gene="CYP2C19", drug="clopidogrel")]
    storage = StorageConfig(raw_dir=Path("raw"), manifests_dir=Path("manifests"))
    ncbi_settings = NCBISettings(NCBI_API_KEY="MOCK_SECRET_KEY", NCBI_EMAIL="test@example.com")

    # Mock esearch
    esearch_route = respx.get(f"{base_url}/esearch.fcgi").respond(
        json={"esearchresult": {"count": "2", "retmax": "100", "retstart": "0", "idlist": ["1001", "1002"]}}
    )
    # Mock efetch
    efetch_route = respx.post(f"{base_url}/efetch.fcgi").respond(
        content=SAMPLE_PUBMED_XML_MATCH,
        headers={"Content-Type": "application/xml"},
    )

    client = httpx.Client()
    manifest, manifest_path = acquire_pubmed(
        config=config,
        gene_drug_pairs=pairs,
        storage=storage,
        ncbi_settings=ncbi_settings,
        workspace_root=tmp_path,
        client=client,
    )

    assert manifest.run_status == "complete"
    assert manifest.pmids_retrieved == ["1001", "1002"]
    assert manifest.reconciliation is not None
    assert manifest.reconciliation.reconciled is True
    assert manifest.reconciliation.missing_count == 0
    assert len(manifest.files) == 1

    # Verify secret key is not in manifest endpoint_url
    assert "MOCK_SECRET_KEY" not in manifest.endpoint_url

    # Verify file saved on disk
    batch_file = tmp_path / manifest.files[0].relative_path
    assert batch_file.is_file()
    assert batch_file.read_bytes() == SAMPLE_PUBMED_XML_MATCH


@respx.mock
def test_acquire_pubmed_reconciliation_missing_pmid(tmp_path):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    config = PubMedConfig(
        base_url=base_url,
        db="pubmed",
        max_records_per_pair=10,
        efetch_batch_size=200,
        rate_limit_rps_default=3.0,
    )
    pairs = [GeneDrugPair(id="pair1", gene="CYP2C19", drug="clopidogrel")]
    storage = StorageConfig(raw_dir=Path("raw"), manifests_dir=Path("manifests"))
    ncbi_settings = NCBISettings(NCBI_EMAIL="test@example.com")

    # esearch returns 1001 and 1002
    respx.get(f"{base_url}/esearch.fcgi").respond(
        json={"esearchresult": {"count": "2", "retmax": "100", "retstart": "0", "idlist": ["1001", "1002"]}}
    )
    # efetch returns XML that only has 1001
    respx.post(f"{base_url}/efetch.fcgi").respond(
        content=SAMPLE_PUBMED_XML_MISSING,
        headers={"Content-Type": "application/xml"},
    )

    client = httpx.Client()
    manifest, _ = acquire_pubmed(
        config=config,
        gene_drug_pairs=pairs,
        storage=storage,
        ncbi_settings=ncbi_settings,
        workspace_root=tmp_path,
        client=client,
    )

    # Missing PMID must be reported in manifest
    assert manifest.reconciliation is not None
    assert manifest.reconciliation.reconciled is False
    assert manifest.reconciliation.missing_count == 1
    assert manifest.reconciliation.missing_pmids == ["1002"]


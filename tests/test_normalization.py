"""
Tests for Phase 2 Stage A: Data contracts, normalization, parsers, and determinism.
Includes Hypothesis property-based tests and unit tests.
"""

import json
from pathlib import Path
import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError

from app.normalization.contracts import (
    EntityRecord,
    SourceProvenance,
    CrossReferenceRecord,
    SynonymRecord,
    RelationshipRecord,
    PublicationRecord,
)
from app.normalization.normalize import (
    normalize_text,
    normalize_search_term,
    split_list_field,
    parse_pubmed_date,
)
from app.normalization.parsers.pubmed import PubMedParser


# ==============================================================================
# 1. HYPOTHESIS PROPERTY TESTS FOR NORMALIZATION
# ==============================================================================

@given(st.text())
def test_normalize_text_idempotence(s: str):
    """normalize_text(normalize_text(s)) == normalize_text(s)"""
    norm1 = normalize_text(s)
    norm2 = normalize_text(norm1)
    assert norm1 == norm2


@given(st.text())
def test_normalize_search_term_idempotence(s: str):
    """normalize_search_term(normalize_search_term(s)) == normalize_search_term(s)"""
    norm1 = normalize_search_term(s)
    norm2 = normalize_search_term(norm1)
    assert norm1 == norm2


def test_normalize_unicode_compatibility():
    """Verify specific Unicode compatibility equivalences."""
    # Ligatures
    assert normalize_text("ﬁle") == "file"
    # Fullwidth characters
    assert normalize_text("CYP２C１９") == "CYP2C19"
    # Search term lowercasing and trimming
    assert normalize_search_term("  CYP2C19*1  ") == "cyp2c19*1"


# ==============================================================================
# 2. DATE PARSING TESTS
# ==============================================================================

@pytest.mark.parametrize(
    "raw_year,raw_month,raw_day,raw_medline,expected_iso,expected_prec",
    [
        ("2020", "05", "12", None, "2020-05-12", "day"),
        ("2020", "May", "12", None, "2020-05-12", "day"),
        ("2020", "May", None, None, "2020-05", "month"),
        ("2020", "05", None, None, "2020-05", "month"),
        ("2020", None, None, None, "2020", "year"),
        (None, None, None, "2019 Spring", "2019", "year"),
        (None, None, None, "2018 Fall-Winter", "2018", "year"),
        (None, None, None, "2017 Jan-Feb", "2017-01", "month"),
        (None, None, None, "2016 May 15-20", "2016-05", "month"),
    ],
)
def test_parse_pubmed_date(raw_year, raw_month, raw_day, raw_medline, expected_iso, expected_prec):
    iso_str, prec = parse_pubmed_date(raw_year, raw_month, raw_day, raw_medline)
    assert iso_str == expected_iso
    assert prec == expected_prec


def test_parse_pubmed_date_unparseable_raises():
    with pytest.raises(ValueError, match="Unparseable publication year"):
        parse_pubmed_date(None, None, None, "Invalid Date Text Without Year")


def test_parse_pubmed_date_never_maps_season_to_month():
    """Ensure season strings are NEVER arbitrarily mapped to months."""
    iso_str, prec = parse_pubmed_date(None, None, None, "2021 Spring")
    assert iso_str == "2021"
    assert prec == "year"

    iso_str2, prec2 = parse_pubmed_date("2021", "Summer", None, None)
    assert iso_str2 == "2021"
    assert prec2 == "year"


# ==============================================================================
# 3. QUOTE-AWARE LIST SPLITTER TESTS
# ==============================================================================

def test_split_list_field_standard():
    raw = '"Aspirin", "Warfarin", Clopidogrel'
    res = split_list_field(raw)
    texts = [item["text"] for item in res]
    assert texts == ["Aspirin", "Warfarin", "Clopidogrel"]
    assert all(not item["is_artifact"] for item in res)


def test_split_list_field_commas_inside_quotes():
    raw = '"Drug A, sodium", "Drug B (oral, tablet)", Drug C'
    res = split_list_field(raw)
    texts = [item["text"] for item in res]
    assert texts == ["Drug A, sodium", "Drug B (oral, tablet)", "Drug C"]
    assert all(not item["is_artifact"] for item in res)


def test_split_list_field_parenthetical_commas_without_quotes():
    raw = 'Drug A (salt, hydrate), Drug B'
    res = split_list_field(raw)
    texts = [item["text"] for item in res]
    # Without quotes, comma inside parentheses is split by CSV reader, and unbalanced parentheses flag is_artifact=True
    assert len(texts) == 3
    # Check that unbalanced parentheses tokens are flagged as artifacts
    assert res[0]["is_artifact"] is True
    assert res[0]["is_split_ambiguous"] is True


def test_split_list_field_malformed_quotes():
    raw = 'Drug A, "Malformed string without closing quote'
    res = split_list_field(raw)
    assert any(item["is_artifact"] for item in res)


# ==============================================================================
# 4. PUBMED PILOT MANIFEST REJECTION GUARD
# ==============================================================================

def test_pubmed_parser_refuses_pilot_manifest(tmp_path):
    pilot_manifest = tmp_path / "manifest_pilot.json"
    pilot_manifest.write_text(
        json.dumps({
            "run_id": "test_pilot",
            "is_pilot": True,
            "batches": []
        }),
        encoding="utf-8"
    )
    with pytest.raises(ValueError, match="PILOT_MANIFEST_REJECTED"):
        PubMedParser(pilot_manifest)


# ==============================================================================
# 5. DATA CONTRACTS VALIDATION
# ==============================================================================

def test_entity_record_contract_validation():
    prov = SourceProvenance(
        source_name="ClinPGx",
        license_text="CC BY-NC-SA 4.0",
        license_check_date="2026-10-31",
        raw_file_path="data/raw/clinpgx/test.zip",
        raw_file_sha256="abcdef123456",
        manifest_run_id="20261030_test",
        record_index=1,
    )
    ent = EntityRecord(
        canonical_id="pg:gene:000001",
        entity_type="gene",
        primary_source_id="PA124",
        display_name="CYP2C19",
        normalized_name="cyp2c19",
        provenance=prov,
    )
    assert ent.canonical_id == "pg:gene:000001"
    assert ent.is_drug is False
    assert ent.defined_by == "primary_definition"

    # Verify immutability (frozen config)
    with pytest.raises(ValidationError):
        ent.canonical_id = "pg:gene:000002"


# ==============================================================================
# 6. PARQUET ROUND-TRIP AND SCHEMA CONFORMANCE
# ==============================================================================

def test_stage_a_parquet_outputs_conformance():
    """Verify generated Parquet tables have valid schemas and non-zero rows."""
    import pyarrow.parquet as pq

    proc_dir = Path("data/processed")
    tables = [
        ("entities.parquet", 12),
        ("cross_references.parquet", 4),
        ("synonyms.parquet", 8),
        ("relationships.parquet", 13),
        ("publications.parquet", 12),
    ]

    for filename, expected_cols in tables:
        file_path = proc_dir / filename
        if not file_path.exists():
            pytest.skip(f"{filename} not yet generated")
        pf = pq.ParquetFile(file_path)
        assert pf.metadata.num_rows > 0, f"{filename} is empty"
        assert len(pf.schema) == expected_cols, f"{filename} expected {expected_cols} cols, got {len(pf.schema)}"


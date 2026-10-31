"""
Tests for Phase 2 Stage A: Data contracts, normalization, parsers, and determinism.
Includes Hypothesis property-based tests and unit tests.
"""

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from app.normalization.contracts import (
    EntityRecord,
    SourceProvenance,
)
from app.normalization.normalize import (
    normalize_search_term,
    normalize_text,
    parse_pubmed_date,
    split_list_field,
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
    raw = "Drug A (salt, hydrate), Drug B"
    res = split_list_field(raw)
    texts = [item["text"] for item in res]
    # Without quotes, comma inside parentheses is split by CSV reader,
    # and unbalanced parentheses flag is_artifact=True
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
        json.dumps({"run_id": "test_pilot", "is_pilot": True, "batches": []}), encoding="utf-8"
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
        assert len(pf.schema) == expected_cols, (
            f"{filename} expected {expected_cols} cols, got {len(pf.schema)}"
        )


# ==============================================================================
# 7. OFFLINE FIXTURES: CLINPGX PARSER, MALFORMED ROWS, & REJECT ACCOUNTING
# ==============================================================================


def test_clinpgx_parser_fixtures_and_accounting(tmp_path):
    """Test ClinPGxParser on isolated synthetic archives with valid and malformed rows."""
    import zipfile

    from app.normalization.parsers.clinpgx import ClinPGxParser

    raw_dir = tmp_path / "clinpgx_raw"
    raw_dir.mkdir()
    haplo_dir = tmp_path / "haplo_raw"
    haplo_dir.mkdir()

    # Create synthetic genes.zip with 1 valid row and 1 malformed row (missing accession)
    hdr = (
        "PharmGKB Accession Id\tSymbol\tName\t"
        "Alternative Names\tAlternative Symbols\tCross-references\n"
    )
    r1 = (
        "PA124\tCYP2C19\tcytochrome P450 family 2 subfamily C member 19\t"
        '"CPC19", "CYPIIC19"\t\tNCBI Gene:1557\n'
    )
    r2 = "\tMISSING_ACC\tTest Gene Without ID\t\t\t\n"
    genes_zip = raw_dir / "genes.zip"
    with zipfile.ZipFile(genes_zip, "w") as z:
        z.writestr("genes.tsv", hdr + r1 + r2)

    parser = ClinPGxParser(
        raw_dir,
        haplo_dir,
        manifest_run_id="test_run",
        haplo_manifest_run_id="test_haplo",
        max_rejection_rate=0.5,  # allow up to 50% for this unit test
    )

    entities, xrefs, synonyms = parser.parse_genes()

    # Verify accounting: raw = accepted + rejected
    stats = parser.accounting["genes"]
    assert stats["raw_rows"] == 2
    assert stats["accepted"] == 1
    assert stats["rejected"] == 1
    assert stats["raw_rows"] == stats["accepted"] + stats["rejected"]

    # Verify valid entity
    assert len(entities) == 1
    assert entities[0].canonical_id == "pg:gene:124"
    assert entities[0].display_name == "CYP2C19"

    # Verify cross references and synonyms
    assert len(xrefs) == 1
    assert xrefs[0].namespace == "NCBI_GENE"
    assert xrefs[0].external_id == "1557"
    assert len(synonyms) == 2

    # Verify reject was recorded
    assert len(parser.rejects["entities"]) == 1
    rej = parser.rejects["entities"][0]
    assert rej["file"] == "genes.tsv"
    assert rej["reason"] == "EMPTY_PRIMARY_ID"
    assert rej["row_index"] == 2


# ==============================================================================
# 8. 0.1% ABORT THRESHOLD ENFORCEMENT
# ==============================================================================


def test_clinpgx_parser_aborts_on_threshold_exceeded(tmp_path):
    """Verify that ClinPGxParser aborts when rejection rate exceeds threshold."""
    import zipfile

    from app.normalization.parsers.clinpgx import ClinPGxParser

    raw_dir = tmp_path / "clinpgx_raw"
    raw_dir.mkdir()
    haplo_dir = tmp_path / "haplo_raw"
    haplo_dir.mkdir()

    # 10 rows: 9 valid, 1 malformed -> 10% rejection rate (> 0.1% threshold)
    genes_zip = raw_dir / "genes.zip"
    header = (
        "PharmGKB Accession Id\tSymbol\tName\t"
        "Alternative Names\tAlternative Symbols\tCross-references"
    )
    with zipfile.ZipFile(genes_zip, "w") as z:
        rows = [header]
        for i in range(1, 10):
            rows.append(f"PA{i}\tGENE{i}\tGene Name {i}\t\t\t")
        rows.append("\tMALFORMED\tMissing ID\t\t\t")
        z.writestr("genes.tsv", "\n".join(rows) + "\n")

    parser = ClinPGxParser(
        raw_dir,
        haplo_dir,
        manifest_run_id="test_run",
        haplo_manifest_run_id="test_haplo",
        max_rejection_rate=0.001,  # strictly 0.1%
    )

    with pytest.raises(ValueError, match="REJECTION_THRESHOLD_EXCEEDED"):
        parser.parse_genes()


# ==============================================================================
# 9. RELATIONSHIPS DANGLING LOGIC
# ==============================================================================


def test_relationships_dangling_logic(tmp_path):
    """Verify relationships dangling detection and relationships_only entity generation."""
    import zipfile

    from app.normalization.parsers.clinpgx import ClinPGxParser

    raw_dir = tmp_path / "clinpgx_raw"
    raw_dir.mkdir()
    haplo_dir = tmp_path / "haplo_raw"
    haplo_dir.mkdir()

    # Create relationships.zip with 2 rows:
    # Row 1: known chemical <-> known gene (resolved edge)
    # Row 2: known chemical <-> unknown phenotype (dangling edge)
    rel_zip = raw_dir / "relationships.zip"
    with zipfile.ZipFile(rel_zip, "w") as z:
        tsv_content = (
            "Entity1_id\tEntity1_name\tEntity1_type\tEntity2_id\tEntity2_name\tEntity2_type\tAssociation\tPMIDs\n"
            "PA449283\tDiazepam\tChemical\tPA124\tCYP2C19\tGene\tassociated\t12345678\n"
            "PA449283\tDiazepam\tChemical\tPA166123456\tSedation\tPhenotype\tassociated\t87654321\n"
        )
        z.writestr("relationships.tsv", tsv_content)

    parser = ClinPGxParser(
        raw_dir,
        haplo_dir,
        manifest_run_id="test_run",
        haplo_manifest_run_id="test_haplo",
    )

    known_ids = {
        ("chemical", "PA449283"): "pg:chem:000001",
        ("gene", "PA124"): "pg:gene:000001",
    }

    records, rel_entities = parser.parse_relationships(known_ids)

    assert len(records) == 2
    # Row 1: resolved
    assert records[0].is_dangling is False
    assert records[0].entity1_canonical_id == "pg:chem:000001"
    assert records[0].entity2_canonical_id == "pg:gene:000001"

    # Row 2: dangling because Phenotype is relationships_only
    assert records[1].is_dangling is True
    assert records[1].entity1_canonical_id == "pg:chem:000001"
    assert records[1].entity2_canonical_id == "pg:phenotype:166123456"

    # Verify synthesized entity
    assert len(rel_entities) == 1
    assert rel_entities[0].canonical_id == "pg:phenotype:166123456"
    assert rel_entities[0].defined_by == "relationships_only"


# ==============================================================================
# 10. CPIC & PUBMED FIXTURES (INCLUDING BOOK ARTICLE)
# ==============================================================================


def test_cpic_parser_fixture_and_reject(tmp_path):
    """Test CPIC parser with 1 valid and 1 malformed record."""
    from app.normalization.parsers.cpic import CPICParser

    cpic_file = tmp_path / "cpic_test.json"
    cpic_data = [
        {
            "allele": {
                "accessionId": "PA165818750",
                "name": "*1",
                "gene": {"symbol": "CYP2C19", "accessionId": "PA124"},
            }
        },
        {"allele": {"name": "NoAccession", "gene": {"symbol": "CYP2C19"}}},
    ]
    cpic_file.write_text(json.dumps(cpic_data), encoding="utf-8")

    parser = CPICParser(cpic_file, manifest_run_id="test_cpic", max_rejection_rate=0.6)
    entities = parser.parse_alleles()

    assert parser.accounting["raw_rows"] == 2
    assert parser.accounting["accepted"] == 1
    assert parser.accounting["rejected"] == 1
    assert len(entities) == 1
    assert entities[0].canonical_id == "pg:haplo:165818750"
    assert entities[0].display_name == "CYP2C19 *1"
    assert len(parser.rejects) == 1
    assert parser.rejects[0]["reason"] == "EMPTY_PRIMARY_ID"


def test_pubmed_parser_article_and_book_article_fixture(tmp_path):
    """Test PubMed parser with standard article, book article, and malformed node."""
    from app.normalization.parsers.pubmed import PubMedParser

    raw_dir = tmp_path / "raw_pubmed" / "test_run"
    raw_dir.mkdir(parents=True)

    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE PubmedArticleSet PUBLIC "-//NLM//DTD PubMedArticle, 1st January 2024//EN" "https://dtd.nlm.nih.gov/ncbi/pubmed/out/pubmed_240101.dtd">
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <Journal>
          <Title>Pharmacogenetics Journal</Title>
          <JournalIssue><PubDate><Year>2021</Year><Month>May</Month><Day>10</Day></PubDate></JournalIssue>
        </Journal>
        <ArticleTitle>Effect of CYP2C19 on Clopidogrel</ArticleTitle>
        <Abstract><AbstractText>This study demonstrates clinical efficacy.</AbstractText></Abstract>
      </Article>
      <MedlineJournalInfo><MedlineTA>Pharmacol</MedlineTA></MedlineJournalInfo>
      <MeshHeadingList>
        <MeshHeading><DescriptorName>Cytochrome P-450 CYP2C19</DescriptorName></MeshHeading>
      </MeshHeadingList>
    </MedlineCitation>
  </PubmedArticle>

  <PubmedBookArticle>
    <BookDocument>
      <PMID>87654321</PMID>
      <ArticleIdList>
        <ArticleId IdType="bookaccession">NBK65798</ArticleId>
      </ArticleIdList>
      <Book>
        <BookTitle>Medical Genetics Summaries</BookTitle>
        <PubDate><Year>2018</Year></PubDate>
      </Book>
      <ArticleTitle>Clopidogrel Therapy and CYP2C19 Genotype</ArticleTitle>
      <Abstract>
        <AbstractText>Bookshelf summary of clinical pharmacogenetics.</AbstractText>
      </Abstract>
    </BookDocument>
  </PubmedBookArticle>

  <PubmedArticle>
    <MedlineCitation>
      <!-- Missing PMID malformed record -->
      <Article><ArticleTitle>Missing PMID Article</ArticleTitle></Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""
    xml_file = raw_dir / "batch_001.xml"
    xml_file.write_text(xml_content, encoding="utf-8")

    manifest_file = tmp_path / "manifest_test.json"
    manifest_file.write_text(
        json.dumps(
            {
                "run_id": "test_run",
                "is_pilot": False,
                "files": [{"relative_path": "batch_001.xml", "sha256": "fake_hash"}],
            }
        ),
        encoding="utf-8",
    )

    parser = PubMedParser(manifest_file, raw_dir=raw_dir, max_rejection_rate=0.5)
    pubs = parser.parse_all_batches()

    assert parser.accounting["raw_rows"] == 3
    assert parser.accounting["accepted"] == 2
    assert parser.accounting["rejected"] == 1

    # Verify standard article
    p1 = [p for p in pubs if p.pmid == "12345678"][0]
    assert p1.record_type == "PubmedArticle"
    assert p1.journal_or_book == "Pharmacogenetics Journal"
    assert p1.pubdate_iso == "2021-05-10"
    assert p1.date_precision == "day"
    assert "Cytochrome P-450 CYP2C19" in p1.mesh_terms

    # Verify book article
    p2 = [p for p in pubs if p.pmid == "87654321"][0]
    assert p2.record_type == "PubmedBookArticle"
    assert p2.journal_or_book == "Medical Genetics Summaries"
    assert p2.book_accession == "NBK65798"
    assert p2.pubdate_iso == "2018"
    assert p2.date_precision == "year"

    # Verify reject log
    assert len(parser.rejects) == 1
    assert parser.rejects[0]["reason"] == "EMPTY_PRIMARY_ID"

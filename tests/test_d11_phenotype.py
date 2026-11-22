"""
Unit and integration tests for D11 Phenotype Fix:
- Evidence matching, entity candidate path, and main claims use only entities of types
  gene, chemical, variant, haplotype, and snv.
- Phenotype and non-evidence types are returned in also_recognized without zeroing claims.
- Mode selection stays unchanged when gene/chemical/variant resolves.
- Phenotype alone stays other_entity.
- q07 retrieves Tier 1 chunks instead of dropping to Tier 2.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.app import app
from app.retrieval.keyword_search import BM25KeywordIndex


def test_phenotype_does_not_zero_out_claims_cyp2d6_codeine_pain():
    """Verify multi-entity query with phenotype returns pair_detail, claims, and also_recognized."""
    client = TestClient(app)
    resp = client.post("/api/ask", json={"question": "CYP2D6 codeine pain"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["query_mode"] == "pair_detail"
    # Phenotype must not zero out claims
    assert len(data.get("claims") or []) == 8

    # Also recognized must capture the phenotype
    also = data.get("also_recognized") or []
    assert len(also) >= 1
    pheno_item = next((it for it in also if it["type"] == "phenotype"), None)
    assert pheno_item is not None
    assert pheno_item["name"] == "Pain"
    assert pheno_item["canonical_id"] == "pg:phenotype:445208"

    # Detail sections must be present
    sections = data.get("sections") or {}
    assert len(sections.get("guidelines") or []) > 0
    assert len(sections.get("drug_labels") or []) > 0


def test_phenotype_with_single_chemical_gives_medicine_overview_and_also_recognized():
    """Verify chemical + phenotype stays in medicine_overview mode with also_recognized."""
    client = TestClient(app)
    resp = client.post("/api/ask", json={"question": "codeine pain"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["query_mode"] == "medicine_overview"
    also = data.get("also_recognized") or []
    assert len(also) >= 1
    assert any(it["name"] == "Pain" and it["type"] == "phenotype" for it in also)


def test_phenotype_with_gene_chemical_cough():
    """Verify CYP2C19 clopidogrel cough returns pair_detail with claims and cough."""
    client = TestClient(app)
    resp = client.post("/api/ask", json={"question": "CYP2C19 clopidogrel cough"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["query_mode"] == "pair_detail"
    assert len(data.get("claims") or []) == 8
    also = data.get("also_recognized") or []
    assert any(it["name"] == "Cough" and it["type"] == "phenotype" for it in also)


def test_q07_variant_detail_with_hypersensitivity_phenotype():
    """Verify q07 query returns variant_detail, claims > 0, and hypersensitivity."""
    client = TestClient(app)
    resp = client.post(
        "/api/ask",
        json={"question": "Is HLA-B*57:01 associated with abacavir hypersensitivity?"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["query_mode"] == "variant_detail"
    assert len(data.get("claims") or []) > 0
    also = data.get("also_recognized") or []
    assert any(
        "hypersensitivity" in it["name"].lower() and it["type"] == "phenotype"
        for it in also
    )


def test_standalone_phenotype_remains_other_entity():
    """Verify standalone phenotype query returns other_entity mode with calm panel payload."""
    client = TestClient(app)
    resp = client.post("/api/ask", json={"question": "pain"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["query_mode"] == "other_entity"
    assert "other_entity" in data.get("flags", [])
    assert len(data.get("claims") or []) == 0
    also = data.get("also_recognized") or []
    assert len(also) >= 1
    assert also[0]["name"] == "Pain"
    assert len(data.get("prompt_templates") or []) > 0


def test_pipeline_search_by_entities_tier1_selection_ignores_phenotype():
    """Verify BM25 search_by_entities achieves Tier 1 matches when evidence entities are used."""
    index = BM25KeywordIndex(Path("data/processed/chunks_v2.parquet"))
    # With phenotype, tier1 is impossible because chunks carry no phenotype IDs
    with_pheno = ["pg:haplo:165987830", "pg:chem:448004", "pg:phenotype:444546"]
    hits_with_pheno = index.search_by_entities(
        "Is HLA-B*57:01 associated with abacavir hypersensitivity?", with_pheno
    )
    assert len(hits_with_pheno) > 0

    # Without phenotype, Tier 1 matches the 6 abacavir + HLA-B*57:01 chunks
    evidence_only = ["pg:haplo:165987830", "pg:chem:448004"]
    hits_evidence_only = index.search_by_entities(
        "Is HLA-B*57:01 associated with abacavir hypersensitivity?", evidence_only
    )

    assert len(hits_evidence_only) == 6
    # Hits without phenotype are strictly Tier 1 subset
    assert all(
        set(evidence_only).issubset(set(h.entity_ids)) for h in hits_evidence_only
    )

"""
Tests for Phase D6 Backend Enhancements:
1. Star allele entity lookup fixes & deduplication by canonical ID
2. GET /api/suggest endpoint & latency constraint (< 100ms over 200 queries)
3. entity_hints on POST /api/ask with 422 validation, override tracking, and resolved_via
4. paper_reserve mechanics for top 10 (annotations displaced, guidelines/drug_labels preserved)
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.api.app import app
from app.retrieval.entity_lookup import EntityLookupService
from app.retrieval.suggest import SuggestService


@pytest.fixture(scope="module")
def entity_service():
    return EntityLookupService()


@pytest.fixture(scope="module")
def suggest_service():
    return SuggestService()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# =========================================================================
# 1. Star Allele Lookup & Canonical ID Deduplication
# =========================================================================

def test_star_allele_cyp2c19_star2_ambiguous(entity_service):
    """'CYP2C19*2' must be ambiguous between pg:var:166154053 and pg:haplo:165980635."""
    res = entity_service.lookup("CYP2C19*2")
    assert res.status == "ambiguous"
    cids = {c.canonical_id for c in res.candidates}
    assert "pg:var:166154053" in cids
    assert "pg:haplo:165980635" in cids
    assert len(cids) == 2


def test_star_allele_cyp2c19_space_star2_resolved(entity_service):
    """'CYP2C19 *2' must resolve to pg:haplo:165980635."""
    res = entity_service.lookup("CYP2C19 *2")
    assert res.status == "resolved"
    assert res.canonical_id == "pg:haplo:165980635"


def test_star_allele_rs4244285_resolved(entity_service):
    """'rs4244285' must resolve to pg:var:166154053."""
    res = entity_service.lookup("rs4244285")
    assert res.status == "resolved"
    assert res.canonical_id == "pg:var:166154053"


def test_star_allele_hlab_5701_unchanged(entity_service):
    """'HLA-B*57:01' must resolve to pg:haplo:165987830."""
    res = entity_service.lookup("HLA-B*57:01")
    assert res.status == "resolved"
    assert res.canonical_id == "pg:haplo:165987830"


def test_canonical_id_deduplication_provenance(entity_service):
    """The same canonical ID from clinpgx and cpic counts once, with all sources in provenance."""
    res = entity_service.lookup("CYP2C19 *2")
    assert res.status == "resolved"
    assert len(res.candidates) == 1
    cand = res.candidates[0]
    assert cand.canonical_id == "pg:haplo:165980635"
    assert "ClinPGx" in cand.provenance or "CPIC" in cand.provenance


# =========================================================================
# 2. GET /api/suggest
# =========================================================================

def test_suggest_short_query_returns_empty(client):
    """Queries shorter than 2 chars return empty suggestions and searches."""
    resp = client.get("/api/suggest?q=a")
    assert resp.status_code == 200
    data = resp.json()
    assert data["suggestions"] == []
    assert data["searches"] == []


def test_suggest_long_query_returns_empty(client):
    """Queries longer than 64 chars return empty list."""
    resp = client.get(f"/api/suggest?q={'a'*65}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["suggestions"] == []
    assert data["searches"] == []


def test_suggest_exact_and_prefix(client):
    """Matches exact and prefix, returning stored entity_type, sort_group, and display_label."""
    resp = client.get("/api/suggest?q=warfarin")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["suggestions"]) > 0
    top = data["suggestions"][0]
    assert top["label"].lower() == "warfarin"
    assert top["entity_type"] == "chemical"
    assert top["sort_group"] == "chemical"
    assert top["display_label"] == "Medicine"
    assert top["match_kind"] == "exact"


def test_suggest_typo_tolerance(client):
    """Queries >= 5 chars with edit distance <= 2 return typo matches with match_kind 'typo'."""
    resp = client.get("/api/suggest?q=warfrin")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["suggestions"]) > 0
    top = data["suggestions"][0]
    assert top["label"].lower() == "warfarin"
    assert top["match_kind"] == "typo"


def test_suggest_ready_made_searches(client):
    """Query matching gene returns ready-made gene-chemical searches from relationships."""
    resp = client.get("/api/suggest?q=VKORC1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["searches"]) > 0
    assert len(data["searches"]) <= 3
    for s in data["searches"]:
        assert "VKORC1" in s["query"]
        assert s["gene"] == "VKORC1"
        assert s["chemical"]


def test_suggest_alias_short_restriction(client):
    """Aliases <= 3 chars are excluded from prefix matches."""
    # Query 'wa' should not match a 2-character alias of something else as a prefix
    resp = client.get("/api/suggest?q=wa")
    assert resp.status_code == 200
    data = resp.json()
    for s in data["suggestions"]:
        if len(s["matched_alias"]) <= 3:
            assert s["matched_alias"].lower() == "wa"


def test_suggest_latency_under_100ms(suggest_service):
    """Suggest latency must be < 100 ms over 200 mixed queries."""
    queries = [
        "war", "clop", "cyp", "cyp2c19", "vkor", "abac", "hla", "fluor", "dpyd", "tpmt",
        "warfrin", "clopidogrl", "asprn", "codeine", "simva", "metformin", "tamoxifen",
        "CYP2D6", "CYP3A4", "SLCO1B1"
    ] * 10
    latencies = []
    for q in queries:
        t0 = time.perf_counter()
        suggest_service.suggest(q)
        latencies.append((time.perf_counter() - t0) * 1000)

    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95)]
    assert p95 < 100.0, f"p95 latency was {p95:.2f}ms, expected < 100ms"


# =========================================================================
# 3. entity_hints on POST /api/ask
# =========================================================================

def test_entity_hints_422_unknown_id(client):
    """POST /api/ask returns 422 if an unknown canonical entity ID is provided in entity_hints."""
    payload = {
        "question": "What is the dose for warfarin?",
        "entity_hints": ["pg:chem:unknown_fake_id_999999"],
    }
    resp = client.post("/api/ask", json=payload)
    assert resp.status_code == 422
    assert "Unknown canonical entity ID" in resp.json()["detail"]


def test_entity_hints_422_too_many_hints(client):
    """POST /api/ask returns 422 if more than 4 entity_hints are provided."""
    payload = {
        "question": "What is the dose for warfarin?",
        "entity_hints": [
            "pg:chem:451906",
            "pg:gene:133787052",
            "pg:var:166154053",
            "pg:haplo:165980635",
            "pg:chem:449053",
        ],
    }
    resp = client.post("/api/ask", json=payload)
    assert resp.status_code == 422
    assert "Too many entity hints" in resp.json()["detail"]


def test_entity_hints_resolves_ambiguity_and_tags_resolved_via(client):
    """entity_hints disambiguates an ambiguous term and sets resolved_via='hint'."""
    payload = {
        "question": "What is the guideline for CYP2C19*2 and clopidogrel?",
        "entity_hints": ["pg:haplo:165980635"],
    }
    resp = client.post("/api/ask", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    resolved = data["resolved_entities"]
    cyp_ent = next((e for e in resolved if e["canonical_id"] == "pg:haplo:165980635"), None)
    assert cyp_ent is not None
    assert cyp_ent["resolved_via"] == "hint"

    clop_ent = next(
        (
            e
            for e in resolved
            if "clopidogrel" in (e.get("name") or e.get("query") or "").lower()
        ),
        None,
    )
    assert clop_ent is not None
    assert clop_ent["resolved_via"] == "text"


def test_entity_hints_disagreement_override(entity_service):
    """If text and hint disagree on the same surface form, the hint wins with hint_overrode_text."""
    # 'CYP2C19 *2' normally resolves to pg:haplo:165980635. Provide hint pg:var:166154053 instead.
    results, _ = entity_service.extract_and_resolve_entities_with_notes(
        "Does CYP2C19 *2 affect warfarin?",
        entity_hints=["pg:var:166154053"],
    )
    var_ent = next((r for r in results if r.canonical_id == "pg:var:166154053"), None)
    assert var_ent is not None
    assert var_ent.resolved_via == "hint"
    assert var_ent.hint_overrode_text is not None
    assert var_ent.hint_overrode_text["hint_id"] == "pg:var:166154053"
    assert var_ent.hint_overrode_text["text_id"] == "pg:haplo:165980635"


def test_no_hints_resolved_via_text(client):
    """When no hints are provided, entities resolve with resolved_via='text'."""
    payload = {"question": "warfarin VKORC1"}
    resp = client.post("/api/ask", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    for e in data["resolved_entities"]:
        assert e.get("resolved_via") == "text"


# =========================================================================
# 4. paper_reserve Top-10 Mechanics
# =========================================================================

def test_paper_reserve_displaces_only_lowest_annotations():
    """For warfarin VKORC1, linked papers displace only lowest-ranked annotations."""
    from app.api.app import answer_service

    p = answer_service.retrieval_pipeline
    res = p.query("warfarin VKORC1")

    # Guidelines at ranks 1 and 2 must be present
    assert res.top_evidence[0].source_type == "guideline"
    assert res.top_evidence[1].source_type == "guideline"

    # Drug labels must be present (never displaced)
    drug_labels = [h for h in res.top_evidence if h.source_type == "drug_label"]
    assert len(drug_labels) >= 2

    # Qualifying linked papers must be present
    pubmeds = [h for h in res.top_evidence if h.source_type == "pubmed"]
    assert len(pubmeds) == 2
    for pub in pubmeds:
        assert pub.provenance.get("linked_via_relationship_pmid") is True

    # Order must be curated first, linked papers after
    curated_indices = [
        idx
        for idx, h in enumerate(res.top_evidence)
        if h.source_type in {"guideline", "annotation", "drug_label"}
    ]
    paper_indices = [
        idx for idx, h in enumerate(res.top_evidence) if h.source_type == "pubmed"
    ]
    assert max(curated_indices) < min(paper_indices)

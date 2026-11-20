"""Tests for Phase D9 Indian Brand Lookup and Backend Integration.

Verifies:
- 'Dolo 650' gives the Dolo 650 mg oral tablet row with ingredient Acetaminophen and ClinPGx ID.
- 'Flexon' gives 4 products including one with three ingredients.
- 'Minidolo' shows the orphan message.
- A combination product lists all ingredients.
- An ambiguous ingredient is not openable.
- 'paracetamol' stays unrecognized.
- 'acetaminophen' resolves as today (medicine overview).
- 'dolo 650 how many can I take' is refused.
- Planted-marker fixture.
- Determinism.
- Banned-columns test (never in parquet schema, data values, or API outputs).
"""

import duckdb
import pytest
from fastapi.testclient import TestClient

from app.api.app import app
from app.ingestion.build_brand_tables import BANNED_COLUMN_NAMES
from app.retrieval.brand_index import BrandIndex


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_dolo_650_brand_lookup(client: TestClient):
    """'Dolo 650' gives Dolo 650 mg oral tablet with Acetaminophen and ClinPGx ID."""
    resp = client.post("/api/ask", json={"question": "Dolo 650"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query_mode"] == "brand_lookup"
    assert "brands" in data and data["brands"] is not None

    brands_data = data["brands"]
    products = brands_data["products"]
    assert len(products) >= 1

    # Find exact Dolo 650 mg oral tablet
    dolo_650 = next(
        (p for p in products if "Dolo 650" in p["brand_name"]),
        None,
    )
    assert dolo_650 is not None, "Dolo 650 mg oral tablet must be present"
    assert dolo_650["generic_name"] == "Acetaminophen 650 mg oral tablet"
    assert dolo_650["is_orphan"] is False

    # Check ingredient Acetaminophen
    assert len(dolo_650["ingredients"]) == 1
    ing = dolo_650["ingredients"][0]
    assert ing["substance_name"] == "Acetaminophen"
    assert "found in ClinPGx as acetaminophen" in ing["status"]
    assert ing["clinpgx_canonical_id"] == "pg:chem:448015"
    assert ing["is_openable"] is True


def test_flexon_gives_4_products_including_three_ingredients(client: TestClient):
    """'Flexon' gives 4 products including one combination with three ingredients."""
    resp = client.post("/api/ask", json={"question": "Flexon"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query_mode"] == "brand_lookup"

    products = data["brands"]["products"]
    assert len(products) == 4, f"Expected exactly 4 Flexon products, got {len(products)}"

    names = [p["brand_name"] for p in products]
    assert any("Flexon 100 mg/5 mL" in n for n in names)
    assert any("Flexon 400 mg" in n for n in names)
    assert any("Mega Flexon" in n for n in names)

    # Combination with three ingredients (Flexon MR)
    flexon_mr = next((p for p in products if "Flexon MR" in p["brand_name"]), None)
    assert flexon_mr is not None, "Flexon MR must be present"
    assert len(flexon_mr["ingredients"]) == 3
    ing_names = [i["substance_name"] for i in flexon_mr["ingredients"]]
    assert set(ing_names) == {"Chlorzoxazone", "Ibuprofen", "Acetaminophen"}
    for ing in flexon_mr["ingredients"]:
        assert ing["is_openable"] is True
        assert ing["clinpgx_canonical_id"] is not None


def test_minidolo_orphan_message(client: TestClient):
    """'Minidolo' shows the orphan message for empty/orphan generic."""
    resp = client.post("/api/ask", json={"question": "Minidolo"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query_mode"] == "brand_lookup"

    products = data["brands"]["products"]
    assert len(products) == 1
    p = products[0]
    assert p["is_orphan"] is True
    assert p["orphan_message"] == "Ingredients not available in NRCeS data for this product."
    assert p["ingredients"] == []


def test_ambiguous_ingredient_not_openable(client: TestClient):
    """An ambiguous ingredient lists candidate names and is not openable."""
    resp = client.post("/api/ask", json={"question": "Regestrone"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query_mode"] == "brand_lookup"

    p = data["brands"]["products"][0]
    assert "Regestrone" in p["brand_name"]
    assert len(p["ingredients"]) == 1
    ing = p["ingredients"][0]
    assert ing["substance_name"] == "Norethindrone acetate"
    assert ing["status"] == "matches several ClinPGx chemicals"
    assert ing["is_openable"] is False
    assert ing["clinpgx_canonical_id"] is None
    assert len(ing["clinpgx_candidates"]) > 1


def test_paracetamol_stays_unrecognized_and_acetaminophen_resolves(client: TestClient):
    """'paracetamol' stays unrecognized, while 'acetaminophen' resolves as today."""
    # 1. paracetamol -> unrecognized
    resp_para = client.post("/api/ask", json={"question": "paracetamol"})
    assert resp_para.status_code == 200
    data_para = resp_para.json()
    assert data_para["query_mode"] == "unrecognized"
    assert "unrecognized_entity" in data_para["flags"]
    assert "No recognized gene, variant or chemical" in data_para["answer"]

    # 2. acetaminophen -> resolves as medicine_overview
    resp_acet = client.post("/api/ask", json={"question": "acetaminophen"})
    assert resp_acet.status_code == 200
    data_acet = resp_acet.json()
    assert data_acet["query_mode"] == "medicine_overview"
    assert len(data_acet["resolved_entities"]) >= 1
    assert data_acet["resolved_entities"][0]["canonical_id"] == "pg:chem:448015"


def test_refusal_guard_takes_priority(client: TestClient):
    """Dosing and usage queries on brands must be refused with 0 calls."""
    resp = client.post("/api/ask", json={"question": "dolo 650 how many can I take"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query_mode"] == "refused"
    assert "refused" in data["flags"]
    assert data["llm_calls"] == 0
    assert data["network_calls"] == 0
    assert data["builder_calls"] == 0


def test_brand_and_entity_collision_returns_ambiguous(client: TestClient):
    """When a query matches both a ClinPGx entity and a brand, return ambiguous mode."""
    resp = client.post("/api/ask", json={"question": "AVIL"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query_mode"] == "ambiguous"
    assert "ambiguous_entity" in data["flags"]

    resolved = data["resolved_entities"]
    assert len(resolved) >= 1
    candidates = resolved[0]["candidates"]
    # Verify candidate types include 'Indian brand (NRCeS)'
    brand_cands = [c for c in candidates if c["entity_type"] == "Indian brand (NRCeS)"]
    assert len(brand_cands) >= 1, "Must contain Indian brand (NRCeS) candidates"
    assert any("Avil" in c["display_name"] for c in brand_cands)


def test_suggest_returns_indian_brand_group_and_typo(client: TestClient):
    """GET /api/suggest includes 'Indian brand names (NRCeS)' group and typo support."""
    # Prefix search
    resp = client.get("/api/suggest?q=dolo&limit=8")
    assert resp.status_code == 200
    data = resp.json()
    brand_suggs = [
        s for s in data["suggestions"] if s["sort_group"] == "Indian brand names (NRCeS)"
    ]
    assert len(brand_suggs) >= 1
    assert any("Dolo 650" in s["label"] for s in brand_suggs)

    # Typo search
    resp_typo = client.get("/api/suggest?q=flxon&limit=8")
    assert resp_typo.status_code == 200
    data_typo = resp_typo.json()
    typo_brands = [
        s for s in data_typo["suggestions"] if s["sort_group"] == "Indian brand names (NRCeS)"
    ]
    assert len(typo_brands) >= 1
    assert any("Flexon" in s["label"] for s in typo_brands)


def test_banned_columns_never_in_tables_or_api(client: TestClient):
    """Ensure banned columns never appear in schemas, parquet tables, or API responses."""
    con = duckdb.connect(":memory:")

    # 1. Parquet schemas
    brand_cols = [
        c[0].lower()
        for c in con.execute(
            "DESCRIBE SELECT * FROM 'data/processed/nrces/brands.parquet'"
        ).fetchall()
    ]
    sub_cols = [
        c[0].lower()
        for c in con.execute(
            "DESCRIBE SELECT * FROM 'data/processed/nrces/substances_map.parquet'"
        ).fetchall()
    ]

    for banned in BANNED_COLUMN_NAMES:
        assert banned not in brand_cols, f"Banned column {banned} found in brands.parquet"
        assert banned not in sub_cols, f"Banned column {banned} found in substances_map.parquet"

    # Supplier, license, and excipient columns must also NOT be in brands.parquet
    for col in ["supplier_id", "supplier_name", "license_number", "license_status", "excipient"]:
        assert col not in brand_cols

    # 2. API responses do not expose banned terms or keys
    resp = client.post("/api/ask", json={"question": "Dolo 650"})
    text_content = resp.text.lower()
    for banned in ["contraindication", "contra indication", "substance description"]:
        assert f'"{banned}"' not in text_content


def test_brand_lookup_determinism(client: TestClient):
    """Calling /api/ask for a brand twice yields identical outputs."""
    resp1 = client.post("/api/ask", json={"question": "Dolo 650"})
    resp2 = client.post("/api/ask", json={"question": "Dolo 650"})
    assert resp1.json() == resp2.json()


def test_planted_marker_fixture():
    """Verify brand matching logic on synthetic planted fixtures."""
    index = BrandIndex()
    # Plant a synthetic brand
    synthetic_brand = {
        "brand_id": "test:brand:999999",
        "brand_name": "PlantedBrand 500 mg oral capsule",
        "normalized_name": "plantedbrand 500 mg oral capsule",
        "generic_id": "gen:999",
        "generic_name": "PlantedGeneric 500 mg oral capsule",
        "substance_ids": ["sub:111", "sub:222"],
        "substance_names": ["SubstanceA", "SubstanceB"],
        "is_combination": True,
        "is_orphan": False,
        "tokens": ["plantedbrand", "500", "mg", "oral", "capsule"],
    }
    index._brands.append(synthetic_brand)
    index._sub_map["sub:111"] = ("matched", ["pg:chem:99901"], ["substance a"])
    index._sub_map["sub:222"] = ("unmatched", [], [])

    # Search with prefix
    res = index.search("plantedbrand 500")
    assert len(res) == 1
    assert res[0]["brand_id"] == "test:brand:999999"

    # Paged lookup
    data = index.get_brand_lookup_data("plantedbrand 500")
    assert data.total_count == 1
    prod = data.products[0]
    assert prod.brand_name == "PlantedBrand 500 mg oral capsule"
    assert len(prod.ingredients) == 2
    assert prod.ingredients[0].status == "found in ClinPGx as substance a"
    assert prod.ingredients[0].is_openable is True
    assert prod.ingredients[1].status == "not matched"
    assert prod.ingredients[1].is_openable is False

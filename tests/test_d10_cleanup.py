"""Tests for Phase D10 Cleanup Pass.

Verifies:
1. Mode consistency and other_entity mode:
   - 'cold and cough', 'pain relief tablets', registry phenotype ('Weight gain'),
     and 'hypersensitivity' return other_entity with other_entity flag, 0 evidence cards,
     0 claims, and prompt templates.
   - Unrecognized query returns unrecognized with unrecognized_entity flag.
2. Stop-word side effects:
   - QUESTION_WORD_STOPLIST does not include gene, genes, drug, drugs, pain, cold.
   - BRAND_TRIGGER_STOPLIST includes those terms.
   - Entity lookup extracts 'pain' as pg:phenotype:445208.
   - Entity lookup on 'CYP2D6 codeine pain' extracts all three entities.
3. Brand index cache:
   - Cache hit on repeated initialization.
   - Invalidation when cache_key or version changes.
   - Corrupted cache falls back to automatic rebuild.
   - Byte-identical results for 30 diverse queries between cached and rebuilt index.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.app import app
from app.retrieval.brand_index import INDEX_VERSION, BrandIndex, compute_cache_key
from app.retrieval.entity_lookup import (
    BRAND_TRIGGER_STOPLIST,
    QUESTION_WORD_STOPLIST,
    EntityLookupService,
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


# ============================================================================
# 1. Mode consistency and other_entity mode
# ============================================================================


@pytest.mark.parametrize(
    "query,expected_entity_names",
    [
        ("cold and cough", ["Cough"]),
        ("pain relief tablets", ["Pain"]),
        ("Weight gain", ["Weight gain"]),
        ("hypersensitivity", ["Hypersensitivity"]),
    ],
)
def test_other_entity_mode_consistent(
    client: TestClient, query: str, expected_entity_names: list[str]
):
    """Entities resolved without dedicated overview mode return other_entity (0 evidence/claims)."""
    resp = client.post("/api/ask", json={"question": query})
    assert resp.status_code == 200
    data = resp.json()

    assert data["query_mode"] == "other_entity"
    assert "other_entity" in data["flags"]
    assert len(data["evidence_bundle"]["items"]) == 0
    assert data["evidence_bundle"]["total_items"] == 0
    assert len(data["claims"]) == 0
    assert data["llm_calls"] == 0
    assert "prompt_templates" in data and len(data["prompt_templates"]) > 0

    resolved = data["resolved_entities"]
    assert len(resolved) >= 1
    found_names = [e["name"] for e in resolved]
    for exp in expected_entity_names:
        assert any(exp.lower() in n.lower() for n in found_names)


def test_unrecognized_mode_when_no_entities_resolved(client: TestClient):
    """When no entities resolve, returns unrecognized with unrecognized_entity flag."""
    resp = client.post("/api/ask", json={"question": "xyzzy123nonexistent"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query_mode"] == "unrecognized"
    assert "unrecognized_entity" in data["flags"]
    assert len(data["resolved_entities"]) == 0
    assert len(data["evidence_bundle"]["items"]) == 0


# ============================================================================
# 2. Stop-word side effects
# ============================================================================


def test_question_words_and_brand_trigger_stoplists_separated():
    """Verify shared stoplist does not contain clinical words, while brand trigger stoplist does."""
    clinical_words = {"gene", "genes", "drug", "drugs", "pain", "cold"}
    for word in clinical_words:
        assert word not in QUESTION_WORD_STOPLIST
        assert word in BRAND_TRIGGER_STOPLIST


def test_entity_resolution_restored():
    """Verify entity extraction extracts pain and handles multi-entity queries."""
    service = EntityLookupService()

    # 'pain' resolves to pg:phenotype:445208
    pain_res = service.extract_and_resolve_entities("pain")
    assert len(pain_res) == 1
    assert pain_res[0].canonical_id == "pg:phenotype:445208"

    # 'cold' does not resolve to any entity
    cold_res = service.extract_and_resolve_entities("cold")
    assert len(cold_res) == 0

    # 'CYP2D6 codeine pain' resolves all three entities
    multi_res = service.extract_and_resolve_entities("CYP2D6 codeine pain")
    cids = {r.canonical_id for r in multi_res}
    assert "pg:gene:128" in cids  # CYP2D6
    assert "pg:chem:449088" in cids  # codeine
    assert "pg:phenotype:445208" in cids  # Pain


# ============================================================================
# 4. Brand Index Cache
# ============================================================================


def test_brand_index_cache_hit_and_atomic_persistence(tmp_path: Path):
    """Verify BrandIndex creates cache on first build and hits cache on second build."""
    cache_root = tmp_path / "cache"

    # Build 1: Cold build creates cache
    idx1 = BrandIndex(cache_root=cache_root, use_cache=True)
    assert len(idx1._brands) > 0

    cache_key = compute_cache_key(idx1.brands_parquet, idx1.substances_parquet, INDEX_VERSION)
    cache_dir = cache_root / cache_key
    assert cache_dir.is_dir()
    assert (cache_dir / "metadata.json").is_file()
    assert (cache_dir / "brands.json").is_file()
    assert (cache_dir / "substances_map.json").is_file()
    assert (cache_dir / "token_to_brand_indices.json").is_file()
    assert (cache_dir / "first_token_to_brand_indices.json").is_file()

    # Build 2: Warm load hits cache
    idx2 = BrandIndex(cache_root=cache_root, use_cache=True)
    assert len(idx2._brands) == len(idx1._brands)
    assert len(idx2._sub_map) == len(idx1._sub_map)


def test_brand_index_cache_invalidation_on_version_or_key_change(tmp_path: Path):
    """Cache is invalidated and rebuilt if index version or hash mismatches."""
    cache_root = tmp_path / "cache"
    idx1 = BrandIndex(cache_root=cache_root, use_cache=True)

    cache_key = compute_cache_key(idx1.brands_parquet, idx1.substances_parquet, INDEX_VERSION)
    meta_file = cache_root / cache_key / "metadata.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8"))

    # Tamper version
    meta["index_version"] = "v_outdated"
    meta_file.write_text(json.dumps(meta), encoding="utf-8")

    # Load should detect mismatch, rebuild, and overwrite with valid version
    idx2 = BrandIndex(cache_root=cache_root, use_cache=True)
    assert len(idx2._brands) == len(idx1._brands)

    rebuilt_meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert rebuilt_meta["index_version"] == INDEX_VERSION


def test_brand_index_cache_corruption_fallback(tmp_path: Path):
    """Corrupted cache files fall back gracefully to DuckDB rebuild."""
    cache_root = tmp_path / "cache"
    idx1 = BrandIndex(cache_root=cache_root, use_cache=True)

    cache_key = compute_cache_key(idx1.brands_parquet, idx1.substances_parquet, INDEX_VERSION)
    brands_file = cache_root / cache_key / "brands.json"

    # Corrupt brands.json with invalid JSON content
    brands_file.write_text("{corrupted json not a list", encoding="utf-8")

    # BrandIndex should catch corruption, fall back to DuckDB rebuild, and write valid cache
    idx2 = BrandIndex(cache_root=cache_root, use_cache=True)
    assert len(idx2._brands) == len(idx1._brands)
    assert isinstance(idx2._brands, list)
    # Check that brands.json is now valid JSON again
    valid_brands = json.loads(brands_file.read_text(encoding="utf-8"))
    assert len(valid_brands) == len(idx1._brands)


def test_byte_identical_results_across_30_queries():
    """Verify byte-identical BrandLookupData results between cached and rebuilt index."""
    idx_cached = BrandIndex(use_cache=True)
    idx_rebuilt = BrandIndex(use_cache=False)

    queries = [
        "dolo 650",
        "dolo",
        "flexon",
        "flexon mr",
        "minidolo",
        "paracetamol",
        "calpol",
        "combiflam",
        "azithral",
        "augmetin",
        "amoxicillin",
        "cetirizine",
        "pantocid",
        "pan 40",
        "omeez",
        "telma 40",
        "atorva",
        "glycomet",
        "ecosprin",
        "crocin",
        "allegra",
        "montair lc",
        "meftal spas",
        "duphaston",
        "shelcal 500",
        "supradyn",
        "becosules",
        "limcee",
        "gelusil",
        "digene",
    ]
    assert len(queries) == 30

    for q in queries:
        res_cached = idx_cached.get_brand_lookup_data(q).model_dump_json()
        res_rebuilt = idx_rebuilt.get_brand_lookup_data(q).model_dump_json()
        assert res_cached == res_rebuilt, f"Results differed for query '{q}'"

"""
Unit tests for Demo D1 retrieval core:
- Biomedical tokenizer preserves rsIDs, star alleles, and HLA names
- Entity resolution handles exact, ambiguous, and unresolved cases
- Reciprocal Rank Fusion (RRF) math and multi-path tracking
- Graph lookup returns stated edge columns and source PMIDs without multi-hop
"""

from pathlib import Path
from typing import Any, Dict, List

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from app.retrieval.chunks import _load_entity_resolver
from app.retrieval.entity_lookup import EntityLookupService
from app.retrieval.fusion import compute_rrf_fusion
from app.retrieval.graph_lookup import RELATIONSHIPS_COLUMNS, GraphLookupService
from app.retrieval.keyword_search import BM25KeywordIndex, KeywordHit
from app.retrieval.meaning_search import MeaningHit
from app.retrieval.tokenizer import tokenize_biomedical


def test_biomedical_tokenizer_preserves_identifiers():
    """Verify tokenizer keeps rsIDs, star alleles, and HLA names intact."""
    text = (
        "Patient with CYP2C19*2, CYP2C9*3 and HLA-B*57:01 treated with clopidogrel, "
        "carrying variant rs12345 and HLA-A*31:01."
    )
    tokens = tokenize_biomedical(text)

    # Identifiers must exist as complete lowercase single tokens
    assert "cyp2c19*2" in tokens
    assert "cyp2c9*3" in tokens
    assert "hla-b*57:01" in tokens
    assert "hla-a*31:01" in tokens
    assert "rs12345" in tokens
    assert "clopidogrel" in tokens

    # Ensure none of the identifiers were split across symbols
    assert "cyp2c19" not in tokens
    assert "57:01" not in tokens
    assert "31:01" not in tokens


def test_entity_lookup_handling():
    """Verify exact lookup, ambiguous collision handling, and unresolved status."""
    service = EntityLookupService()

    # 1. Exact known gene
    res_gene = service.lookup("CYP2C19")
    assert res_gene.status == "resolved"
    assert res_gene.canonical_id is not None
    assert any(t.lower() == "gene" for t in res_gene.candidate_types)

    # 2. Exact known drug
    res_drug = service.lookup("clopidogrel")
    assert res_drug.status == "resolved"
    assert res_drug.canonical_id is not None
    assert any(t.lower() == "chemical" for t in res_drug.candidate_types)

    # 3. Known ambiguous name (e.g. 'DBI' collides between Chemical 'phenformin' and Gene 'DBI')
    res_ambig = service.lookup("DBI")
    assert res_ambig.status == "ambiguous"
    assert len(res_ambig.candidate_types) >= 2
    assert any(t.lower() == "gene" for t in res_ambig.candidate_types)
    assert any(t.lower() == "chemical" for t in res_ambig.candidate_types)
    assert len(res_ambig.candidates) >= 2

    # 4. Completely unknown name
    res_unknown = service.lookup("NON_EXISTENT_PHARMA_TERM_XYZ_999")
    assert res_unknown.status == "unresolved"
    assert res_unknown.canonical_id is None
    assert len(res_unknown.candidates) == 0


def test_rrf_fusion_correctness():
    """Verify Reciprocal Rank Fusion calculation and provenance path attribution."""
    k = 60

    # Mock keyword hits
    kw_hits = [
        KeywordHit(
            chunk_id="chunk:1",
            source_type="pubmed",
            source_id="1001",
            title="Paper 1",
            content="Content 1",
            date="2020-01-01",
            date_precision="day",
            bm25_score=5.0,
            rank=1,
        ),
        KeywordHit(
            chunk_id="chunk:2",
            source_type="annotation",
            source_id="2001",
            title="Annotation 1",
            content="Content 2",
            date="unknown",
            date_precision="unknown",
            bm25_score=3.0,
            rank=2,
        ),
    ]

    # Mock meaning hits
    meaning_hits = [
        MeaningHit(
            chunk_id="chunk:2",  # Present in both
            source_type="annotation",
            source_id="2001",
            title="Annotation 1",
            content="Content 2",
            date="unknown",
            date_precision="unknown",
            dense_score=0.9,
            rank=1,
        ),
        MeaningHit(
            chunk_id="chunk:3",
            source_type="guideline",
            source_id="3001",
            title="Guideline 1",
            content="Content 3",
            date="2021-05",
            date_precision="month",
            dense_score=0.8,
            rank=2,
        ),
    ]

    # Mock graph chunk
    graph_chunks: List[Dict[str, Any]] = [
        {
            "chunk_id": "chunk:1",  # Present in keyword and graph
            "source_type": "pubmed",
            "source_id": "1001",
            "title": "Paper 1",
            "content": "Content 1",
            "date": "2020-01-01",
            "date_precision": "day",
            "entity_ids": [],
        }
    ]

    fused = compute_rrf_fusion(
        keyword_hits=kw_hits,
        meaning_hits=meaning_hits,
        graph_chunks=graph_chunks,
        k=k,
        top_n=5,
    )

    assert len(fused) == 3

    # Check chunk:1: in keyword (rank 1) and graph (rank 1)
    # Expected score: 1/(60+1) + 1/(60+1) = 2/61 ≈ 0.0327868
    chunk1_res = next(f for f in fused if f.chunk_id == "chunk:1")
    expected_chunk1_score = (1.0 / (k + 1)) + (1.0 / (k + 1))
    assert pytest.approx(chunk1_res.rrf_score, 1e-5) == expected_chunk1_score
    assert set(chunk1_res.found_by_paths) == {"keyword", "graph"}

    # Check chunk:2: in keyword (rank 2) and meaning (rank 1)
    # Expected score: 1/(60+2) + 1/(60+1) = 1/62 + 1/61 ≈ 0.0325215
    chunk2_res = next(f for f in fused if f.chunk_id == "chunk:2")
    expected_chunk2_score = (1.0 / (k + 2)) + (1.0 / (k + 1))
    assert pytest.approx(chunk2_res.rrf_score, 1e-5) == expected_chunk2_score
    assert set(chunk2_res.found_by_paths) == {"keyword", "meaning"}

    # Check chunk:3: in meaning only (rank 2)
    # Expected score: 1/(60+2) = 1/62 ≈ 0.016129
    chunk3_res = next(f for f in fused if f.chunk_id == "chunk:3")
    assert pytest.approx(chunk3_res.rrf_score, 1e-5) == (1.0 / (k + 2))
    assert chunk3_res.found_by_paths == ["meaning"]


def test_graph_lookup_returns_sources():
    """Verify graph lookup returns stated edge fields and explicit source PMIDs."""
    service = GraphLookupService()

    # Look up direct relationship between CYP2C19 and clopidogrel
    # First resolve them to canonical IDs
    entity_service = EntityLookupService()
    cyp2c19_res = entity_service.lookup("CYP2C19")
    clopidogrel_res = entity_service.lookup("clopidogrel")

    assert cyp2c19_res.status == "resolved" and cyp2c19_res.canonical_id is not None
    assert clopidogrel_res.status == "resolved" and clopidogrel_res.canonical_id is not None

    lookup_res = service.lookup_edges([cyp2c19_res.canonical_id, clopidogrel_res.canonical_id])

    # Must return exact documented columns
    assert lookup_res.columns_used == RELATIONSHIPS_COLUMNS
    assert len(lookup_res.edges) > 0

    # Every returned edge must have valid association and non-empty PMIDs
    for edge in lookup_res.edges:
        assert edge.association != ""
        assert len(edge.pmids) > 0
        assert (
            (
                edge.entity1_canonical_id == cyp2c19_res.canonical_id
                and edge.entity2_canonical_id == clopidogrel_res.canonical_id
            )
            or (
                edge.entity1_canonical_id == clopidogrel_res.canonical_id
                and edge.entity2_canonical_id == cyp2c19_res.canonical_id
            )
        )


def test_bm25_filters_stopwords_and_ranks_biomedical_terms(tmp_path: Path):
    """Verify BM25KeywordIndex filters stopwords so prose filler never outranks entities."""
    chunks_path = tmp_path / "chunks.parquet"
    schema = pa.schema(
        [
            ("chunk_id", pa.string()),
            ("source_type", pa.string()),
            ("source_id", pa.string()),
            ("title", pa.string()),
            ("content", pa.string()),
            ("date", pa.string()),
            ("date_precision", pa.string()),
            ("entity_ids", pa.list_(pa.string())),
        ]
    )
    rows = [
        {
            "chunk_id": "chunk:pubmed:1",
            "source_type": "pubmed",
            "source_id": "1",
            "title": "The relationship between unrelated proteins and drugs",
            "content": "What is the relationship between other unrelated factors and biomarkers.",
            "date": "2020-01-01",
            "date_precision": "day",
            "entity_ids": [],
        },
        {
            "chunk_id": "chunk:annotation:2",
            "source_type": "annotation",
            "source_id": "2",
            "title": "CYP2C19 - clopidogrel",
            "content": "CYP2C19*2 allele is associated with altered clopidogrel metabolism.",
            "date": "unknown",
            "date_precision": "unknown",
            "entity_ids": ["pg:gene:124", "pg:chem:449053"],
        },
        {
            "chunk_id": "chunk:annotation:3",
            "source_type": "annotation",
            "source_id": "3",
            "title": "TPMT - azathioprine",
            "content": "TPMT deficiency increases risk of azathioprine toxicity.",
            "date": "2020-05-01",
            "date_precision": "day",
            "entity_ids": ["pg:gene:356", "pg:chem:448515"],
        },
        {
            "chunk_id": "chunk:annotation:4",
            "source_type": "annotation",
            "source_id": "4",
            "title": "DPYD - fluorouracil",
            "content": "DPYD decreased function variants increase fluorouracil toxicity.",
            "date": "2021-01-15",
            "date_precision": "day",
            "entity_ids": ["pg:gene:145", "pg:chem:449657"],
        },
    ]
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), chunks_path)

    idx = BM25KeywordIndex(chunks_path=chunks_path)
    hits = idx.search("What is the relationship between CYP2C19 and clopidogrel?", top_k=5)
    assert len(hits) == 1
    assert hits[0].chunk_id == "chunk:annotation:2"

    # Stopword-only query returns empty list
    assert idx.search("What is the relationship between", top_k=5) == []


def test_graph_lookup_splits_semicolon_pmids(tmp_path: Path):
    """Verify semicolon-joined PMID strings in relationships.parquet split cleanly."""
    rels_path = tmp_path / "relationships.parquet"
    schema = pa.schema(
        [
            ("relationship_id", pa.string()),
            ("entity1_id", pa.string()),
            ("entity1_name", pa.string()),
            ("entity1_type", pa.string()),
            ("entity1_canonical_id", pa.string()),
            ("entity2_id", pa.string()),
            ("entity2_name", pa.string()),
            ("entity2_type", pa.string()),
            ("entity2_canonical_id", pa.string()),
            ("association", pa.string()),
            ("pmids", pa.list_(pa.string())),
            ("is_dangling", pa.bool_()),
            ("raw_file_sha256", pa.string()),
        ]
    )
    rows = [
        {
            "relationship_id": "rel:test01",
            "entity1_id": "PA124",
            "entity1_name": "CYP2C19",
            "entity1_type": "Gene",
            "entity1_canonical_id": "pg:gene:124",
            "entity2_id": "PA449053",
            "entity2_name": "clopidogrel",
            "entity2_type": "Chemical",
            "entity2_canonical_id": "pg:chem:449053",
            "association": "associated",
            "pmids": ["11111111;22222222;33333333"],
            "is_dangling": False,
            "raw_file_sha256": "deadbeef",
        }
    ]
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), rels_path)

    svc = GraphLookupService(processed_dir=tmp_path)
    res = svc.lookup_edges(["pg:gene:124", "pg:chem:449053"])
    assert len(res.edges) == 1
    assert res.edges[0].pmids == ["11111111", "22222222", "33333333"]
    assert res.source_pmids == ["11111111", "22222222", "33333333"]


def test_chunks_resolver_handles_pa_accessions_and_records_matched_entities(tmp_path: Path):
    """Verify explicit entity resolver handles PA prefixes without inferring PubMed links."""
    entities_path = tmp_path / "entities.parquet"
    synonyms_path = tmp_path / "synonyms.parquet"
    ent_schema = pa.schema(
        [
            ("canonical_id", pa.string()),
            ("display_name", pa.string()),
            ("normalized_name", pa.string()),
            ("primary_source_id", pa.string()),
            ("entity_type", pa.string()),
        ]
    )
    syn_schema = pa.schema(
        [
            ("canonical_id", pa.string()),
            ("synonym_text", pa.string()),
            ("normalized_synonym", pa.string()),
            ("synonym_type", pa.string()),
        ]
    )
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "canonical_id": "pg:gene:124",
                    "display_name": "CYP2C19",
                    "normalized_name": "cyp2c19",
                    "primary_source_id": "PA124",
                    "entity_type": "gene",
                }
            ],
            schema=ent_schema,
        ),
        entities_path,
    )
    pq.write_table(pa.Table.from_pylist([], schema=syn_schema), synonyms_path)

    resolve_fn = _load_entity_resolver(tmp_path)
    assert resolve_fn("PA124", "gene") == "pg:gene:124"
    assert resolve_fn("124", "gene") == "pg:gene:124"
    assert resolve_fn("CYP2C19", "gene") == "pg:gene:124"

    # Simulate matched_entities assignment: structured IDs match, empty PubMed stays empty
    resolved_cids = ["pg:gene:124", "pg:chem:449053"]
    fused = compute_rrf_fusion(
        keyword_hits=[
            KeywordHit(
                chunk_id="c1",
                source_type="guideline",
                source_id="PA166104948",
                title="CPIC Guideline",
                content="Guideline content",
                date="2022-01-01",
                date_precision="day",
                entity_ids=["pg:gene:124", "pg:chem:449053"],
                bm25_score=5.0,
                rank=1,
            ),
            KeywordHit(
                chunk_id="c2",
                source_type="pubmed",
                source_id="35016407",
                title="CYP2C19 and clopidogrel",
                content="Abstract text without structured entity_ids.",
                date="2022-01-01",
                date_precision="day",
                entity_ids=[],
                bm25_score=4.5,
                rank=2,
            ),
        ],
        meaning_hits=[],
        graph_chunks=[],
        k=60,
        top_n=10,
    )
    for hit in fused:
        hit.matched_entities = [cid for cid in resolved_cids if cid in hit.entity_ids]
    by_id = {h.source_id: h for h in fused}
    assert by_id["PA166104948"].matched_entities == ["pg:gene:124", "pg:chem:449053"]
    assert by_id["35016407"].matched_entities == []


def test_meaning_index_checkpoint_resume_and_verify(tmp_path: Path, monkeypatch):
    """Verify MeaningSearchIndex checkpoint, restart/resume without duplicates, and verify."""
    import json

    import numpy as np

    from app.retrieval.meaning_search import MeaningSearchIndex, compute_embedded_text_sha256

    encoded_batches: List[List[str]] = []

    class _FakeEncoder:
        def __init__(self, model_name: str):
            self.model_name = model_name

        def get_embedding_dimension(self) -> int:
            return 4

        def encode(self, texts, batch_size=16, show_progress_bar=False, normalize_embeddings=True):
            encoded_batches.append(list(texts))
            vecs = []
            for idx, _t in enumerate(texts):
                v = np.array([1.0, float(idx + 1), 0.5, 0.25], dtype=np.float32)
                v = v / np.linalg.norm(v)
                vecs.append(v)
            return np.vstack(vecs)

    monkeypatch.setattr("app.retrieval.meaning_search.SentenceTransformer", _FakeEncoder)

    chunks_path = tmp_path / "chunks.parquet"
    schema = pa.schema(
        [
            ("chunk_id", pa.string()),
            ("source_type", pa.string()),
            ("source_id", pa.string()),
            ("title", pa.string()),
            ("content", pa.string()),
            ("date", pa.string()),
            ("date_precision", pa.string()),
            ("entity_ids", pa.list_(pa.string())),
        ]
    )
    rows = [
        {
            "chunk_id": f"chunk:test:{i:02d}",
            "source_type": "annotation" if i % 2 == 0 else "pubmed",
            "source_id": f"S{i:02d}",
            "title": f"Title {i}",
            "content": f"Content {i}",
            "date": "2022-01-01" if i % 2 == 1 else "unknown",
            "date_precision": "day" if i % 2 == 1 else "unknown",
            "entity_ids": ["pg:gene:124"] if i % 2 == 0 else [],
        }
        for i in range(10)
    ]
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), chunks_path)
    expected_sha = compute_embedded_text_sha256(chunks_path)

    qdrant_dir = tmp_path / "qdrant_db"

    # Part 1: Build only 2 batches (4 items with batch_size=2) and stop cleanly
    idx1 = MeaningSearchIndex(
        model_name="BAAI/bge-small-en-v1.5",
        qdrant_path=qdrant_dir,
        chunks_path=chunks_path,
    )
    count_partial = idx1.build_index(
        force_rebuild=True, batch_size=2, checkpoint_every=1, max_batches=2
    )
    assert count_partial == 4
    assert idx1.checkpoint_path.exists()
    assert not idx1.manifest_path.exists()
    ckpt = json.loads(idx1.checkpoint_path.read_text(encoding="utf-8"))
    assert ckpt["next_idx"] == 4
    assert ckpt["embedded_text_sha256"] == expected_sha
    idx1.close()

    # Clear call tracker and simulate a fresh process resuming from disk
    encoded_batches.clear()
    idx2 = MeaningSearchIndex(
        model_name="BAAI/bge-small-en-v1.5",
        qdrant_path=qdrant_dir,
        chunks_path=chunks_path,
    )
    count_full = idx2.build_index(force_rebuild=False, batch_size=2, checkpoint_every=1)
    assert count_full == 10
    # Only the remaining 6 items (3 batches of 2) should have been encoded
    assert sum(len(b) for b in encoded_batches) == 6
    assert not idx2.checkpoint_path.exists()
    assert idx2.manifest_path.exists()

    manifest = json.loads(idx2.manifest_path.read_text(encoding="utf-8"))
    assert manifest["total_points"] == 10
    assert manifest["embedded_text_sha256"] == expected_sha
    assert manifest["model_version"] == "1.5"
    assert manifest["points_per_source_type"] == {"annotation": 5, "pubmed": 5}

    report = idx2.verify_index()
    assert report["is_exact_match"] is True
    assert report["unique_chunk_ids"] == 10
    assert report["duplicate_count"] == 0
    idx2.close()


def test_meaning_index_staged_append_and_verify(tmp_path: Path, monkeypatch):
    """
    Verify two-stage Qdrant build with --source-types:
    Stage 1 (annotation,drug_label,guideline) followed by Stage 2 (pubmed)
    appends without recreating or overwriting Stage 1 points, updates per-type
    completeness in manifest, and verifies both per-stage and full-corpus 1:1 matches.
    """
    import json

    import numpy as np

    from app.retrieval.meaning_search import MeaningSearchIndex

    class _FakeEncoder:
        def __init__(self, model_name: str):
            self.model_name = model_name

        def get_embedding_dimension(self) -> int:
            return 4

        def encode(self, texts, batch_size=16, show_progress_bar=False, normalize_embeddings=True):
            vecs = []
            for idx, _t in enumerate(texts):
                v = np.array([1.0, float(idx + 1), 0.5, 0.25], dtype=np.float32)
                v = v / np.linalg.norm(v)
                vecs.append(v)
            return np.vstack(vecs)

    monkeypatch.setattr("app.retrieval.meaning_search.SentenceTransformer", _FakeEncoder)

    chunks_path = tmp_path / "chunks.parquet"
    schema = pa.schema(
        [
            ("chunk_id", pa.string()),
            ("source_type", pa.string()),
            ("source_id", pa.string()),
            ("title", pa.string()),
            ("content", pa.string()),
            ("date", pa.string()),
            ("date_precision", pa.string()),
            ("entity_ids", pa.list_(pa.string())),
        ]
    )
    rows = [
        {
            "chunk_id": "chunk:guideline:G1",
            "source_type": "guideline",
            "source_id": "G1",
            "title": "Guideline 1",
            "content": "Guideline content one",
            "date": "2022-01-01",
            "date_precision": "day",
            "entity_ids": ["pg:gene:124"],
        },
        {
            "chunk_id": "chunk:drug_label:L1",
            "source_type": "drug_label",
            "source_id": "L1",
            "title": "Label 1",
            "content": "Drug label content",
            "date": "2021-01-01",
            "date_precision": "day",
            "entity_ids": ["pg:chem:449053"],
        },
        {
            "chunk_id": "chunk:annotation:A1",
            "source_type": "annotation",
            "source_id": "A1",
            "title": "Ann 1",
            "content": "Annotation one",
            "date": "unknown",
            "date_precision": "unknown",
            "entity_ids": ["pg:gene:124", "pg:chem:449053"],
        },
        {
            "chunk_id": "chunk:annotation:A2",
            "source_type": "annotation",
            "source_id": "A2",
            "title": "Ann 2",
            "content": "Annotation two longer text",
            "date": "unknown",
            "date_precision": "unknown",
            "entity_ids": ["pg:gene:124"],
        },
        {
            "chunk_id": "chunk:pubmed:P1:0",
            "source_type": "pubmed",
            "source_id": "900001",
            "title": "PubMed 1",
            "content": "Abstract text one",
            "date": "2020-05-01",
            "date_precision": "day",
            "entity_ids": [],
        },
        {
            "chunk_id": "chunk:pubmed:P2:0",
            "source_type": "pubmed",
            "source_id": "900002",
            "title": "PubMed 2",
            "content": "Abstract text two longer",
            "date": "2021-06-01",
            "date_precision": "day",
            "entity_ids": [],
        },
    ]
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), chunks_path)

    qdrant_dir = tmp_path / "qdrant_db_full"
    idx = MeaningSearchIndex(
        model_name="BAAI/bge-small-en-v1.5",
        qdrant_path=qdrant_dir,
        chunks_path=chunks_path,
    )

    # Stage 1: annotation, drug_label, guideline (4 points total)
    c1 = idx.build_index(
        force_rebuild=False,
        batch_size=2,
        checkpoint_every=1,
        source_types=["annotation", "drug_label", "guideline"],
    )
    assert c1 == 4
    manifest_s1 = json.loads(idx.manifest_path.read_text(encoding="utf-8"))
    assert manifest_s1["points_per_source_type"] == {
        "annotation": 2,
        "drug_label": 1,
        "guideline": 1,
        "pubmed": 0,
    }
    assert manifest_s1["complete_per_source_type"] == {
        "annotation": True,
        "drug_label": True,
        "guideline": True,
        "pubmed": False,
    }
    rep_s1 = idx.verify_index(source_types=["annotation", "drug_label", "guideline"])
    assert rep_s1["is_exact_match"] is True
    assert rep_s1["coverage_per_source_type"]["pubmed"]["complete"] is False

    # Coverage summary while partial
    cov_s1 = idx.get_coverage_summary(force_refresh=True)
    assert cov_s1["is_partial"] is True
    assert cov_s1["covered_source_types"] == ["annotation", "drug_label", "guideline"]

    # Stage 2: pubmed appended cleanly without wiping Stage 1
    c2 = idx.build_index(
        force_rebuild=False,
        batch_size=2,
        checkpoint_every=1,
        source_types=["pubmed"],
    )
    assert c2 == 6
    manifest_s2 = json.loads(idx.manifest_path.read_text(encoding="utf-8"))
    assert manifest_s2["complete_per_source_type"] == {
        "annotation": True,
        "drug_label": True,
        "guideline": True,
        "pubmed": True,
    }
    rep_s2 = idx.verify_index(source_types=["pubmed"])
    assert rep_s2["is_exact_match"] is True
    rep_full = idx.verify_index()
    assert rep_full["is_exact_match"] is True
    assert rep_full["qdrant_count"] == 6
    assert rep_full["duplicate_count"] == 0
    cov_full = idx.get_coverage_summary(force_refresh=True)
    assert cov_full["is_partial"] is False
    idx.close()


def test_entity_lookup_stoplist_and_uppercase_alpha_gene_rule():
    """
    Verify Section C extraction rules against the real ClinPGx registry:
    - 'impact' does not resolve from free text (stoplist + lowercase <=6 alpha gene)
    - 'IMPACT' resolves to pg:gene:143485502
    - 'vkorc1' lowercase still resolves (contains a digit)
    - 'cat' lowercase does not resolve as a gene and flags possible_gene_name_lowercase
    - entity_hints resolves explicit canonical IDs even if free text has lowercase name
    """
    service = EntityLookupService()

    res_impact_lower, notes_impact = service.extract_and_resolve_entities_with_notes("impact")
    assert res_impact_lower == []
    assert notes_impact == []

    res_q05, notes_q05 = service.extract_and_resolve_entities_with_notes(
        "What clinical impact does CYP2C19*2 have on clopidogrel efficacy?"
    )
    resolved_q05_ids = {r.canonical_id for r in res_q05 if r.canonical_id}
    assert "pg:gene:143485502" not in resolved_q05_ids
    assert "pg:chem:449053" in resolved_q05_ids
    assert notes_q05 == []

    res_impact_upper, _ = service.extract_and_resolve_entities_with_notes("IMPACT")
    assert len(res_impact_upper) == 1
    assert res_impact_upper[0].canonical_id == "pg:gene:143485502"

    res_vkorc1_lower, _ = service.extract_and_resolve_entities_with_notes("vkorc1")
    assert len(res_vkorc1_lower) == 1
    assert res_vkorc1_lower[0].canonical_id == "pg:gene:133787052"

    res_cat_lower, notes_cat = service.extract_and_resolve_entities_with_notes("cat")
    assert res_cat_lower == []
    assert notes_cat == ["cat"]

    res_cat_hint, notes_cat_hint = service.extract_and_resolve_entities_with_notes(
        "cat", entity_hints=["pg:gene:26099"]
    )
    assert len(res_cat_hint) == 1
    assert res_cat_hint[0].canonical_id == "pg:gene:26099"
    assert notes_cat_hint == []


def test_pubmed_relationship_pmid_linking_strictness(tmp_path: Path, monkeypatch):
    """
    Verify Section D strict PubMed PMID linking:
    - A PubMed paper listed on NO resolved-pair edge is NEVER linked.
    - Unindexed PMIDs listed on an edge create NO stub/fake items.
    - A PubMed chunk whose PMID IS listed on a resolved-pair edge receives matched_entities
      strictly from that edge's resolved endpoints plus relationship_id provenance.
    """
    import numpy as np

    from app.retrieval.config import RetrievalConfig
    from app.retrieval.pipeline import RetrievalPipeline

    class _FakeEncoder:
        def __init__(self, model_name: str):
            self.model_name = model_name

        def get_embedding_dimension(self) -> int:
            return 4

        def encode(self, texts, batch_size=16, show_progress_bar=False, normalize_embeddings=True):
            vecs = []
            for idx, _t in enumerate(texts):
                v = np.array([1.0, float(idx + 1), 0.5, 0.25], dtype=np.float32)
                v = v / np.linalg.norm(v)
                vecs.append(v)
            return np.vstack(vecs)

    monkeypatch.setattr("app.retrieval.meaning_search.SentenceTransformer", _FakeEncoder)

    # 1. Entities & empty synonyms
    entities_schema = pa.schema(
        [
            ("canonical_id", pa.string()),
            ("entity_type", pa.string()),
            ("primary_source_id", pa.string()),
            ("display_name", pa.string()),
            ("normalized_name", pa.string()),
            ("is_drug", pa.bool_()),
            ("gene_symbol", pa.string()),
            ("defined_by", pa.string()),
            ("is_ambiguous", pa.bool_()),
        ]
    )
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "canonical_id": "pg:gene:124",
                    "entity_type": "gene",
                    "primary_source_id": "PA124",
                    "display_name": "CYP2C19",
                    "normalized_name": "cyp2c19",
                    "is_drug": False,
                    "gene_symbol": "CYP2C19",
                    "defined_by": "clinpgx_genes",
                    "is_ambiguous": False,
                },
                {
                    "canonical_id": "pg:chem:449053",
                    "entity_type": "chemical",
                    "primary_source_id": "PA449053",
                    "display_name": "clopidogrel",
                    "normalized_name": "clopidogrel",
                    "is_drug": True,
                    "gene_symbol": None,
                    "defined_by": "clinpgx_chemicals",
                    "is_ambiguous": False,
                },
            ],
            schema=entities_schema,
        ),
        tmp_path / "entities.parquet",
    )
    syn_schema = pa.schema(
        [
            ("canonical_id", pa.string()),
            ("synonym_text", pa.string()),
            ("normalized_synonym", pa.string()),
            ("synonym_type", pa.string()),
        ]
    )
    pq.write_table(pa.Table.from_pylist([], schema=syn_schema), tmp_path / "synonyms.parquet")

    # 2. Relationships: one pair edge citing indexed PMID 111111 + unindexed PMID 999999,
    # and one single-entity edge citing PMID 222222 whose second endpoint is NOT resolved
    rel_schema = pa.schema(
        [
            ("relationship_id", pa.string()),
            ("entity1_id", pa.string()),
            ("entity1_name", pa.string()),
            ("entity1_type", pa.string()),
            ("entity1_canonical_id", pa.string()),
            ("entity2_id", pa.string()),
            ("entity2_name", pa.string()),
            ("entity2_type", pa.string()),
            ("entity2_canonical_id", pa.string()),
            ("association", pa.string()),
            ("pmids", pa.list_(pa.string())),
            ("is_dangling", pa.bool_()),
            ("raw_file_sha256", pa.string()),
        ]
    )
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "relationship_id": "rel:pair01",
                    "entity1_id": "PA124",
                    "entity1_name": "CYP2C19",
                    "entity1_type": "Gene",
                    "entity1_canonical_id": "pg:gene:124",
                    "entity2_id": "PA449053",
                    "entity2_name": "clopidogrel",
                    "entity2_type": "Chemical",
                    "entity2_canonical_id": "pg:chem:449053",
                    "association": "associated",
                    "pmids": ["111111", "999999"],
                    "is_dangling": False,
                    "raw_file_sha256": "sha1",
                },
                {
                    "relationship_id": "rel:other01",
                    "entity1_id": "PA124",
                    "entity1_name": "CYP2C19",
                    "entity1_type": "Gene",
                    "entity1_canonical_id": "pg:gene:124",
                    "entity2_id": "PA999999",
                    "entity2_name": "omeprazole",
                    "entity2_type": "Chemical",
                    "entity2_canonical_id": "pg:chem:999999",
                    "association": "associated",
                    "pmids": ["222222"],
                    "is_dangling": False,
                    "raw_file_sha256": "sha2",
                },
            ],
            schema=rel_schema,
        ),
        tmp_path / "relationships.parquet",
    )

    # 3. Chunks: linked 111111, unlinked 222222, unlinked 333333 (PMID 999999 absent)
    chunks_schema = pa.schema(
        [
            ("chunk_id", pa.string()),
            ("source_type", pa.string()),
            ("source_id", pa.string()),
            ("title", pa.string()),
            ("content", pa.string()),
            ("date", pa.string()),
            ("date_precision", pa.string()),
            ("entity_ids", pa.list_(pa.string())),
        ]
    )
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "chunk_id": "chunk:pubmed:111111:0",
                    "source_type": "pubmed",
                    "source_id": "111111",
                    "title": "CYP2C19 and clopidogrel study",
                    "content": "Abstract discussing CYP2C19 and clopidogrel.",
                    "date": "2019-03-01",
                    "date_precision": "day",
                    "entity_ids": [],
                },
                {
                    "chunk_id": "chunk:pubmed:222222:0",
                    "source_type": "pubmed",
                    "source_id": "222222",
                    "title": "CYP2C19 and omeprazole",
                    "content": "Abstract mentioning CYP2C19 and clopidogrel comparator.",
                    "date": "2020-01-01",
                    "date_precision": "day",
                    "entity_ids": [],
                },
                {
                    "chunk_id": "chunk:pubmed:333333:0",
                    "source_type": "pubmed",
                    "source_id": "333333",
                    "title": "Unrelated paper",
                    "content": "CYP2C19 and clopidogrel background mention only.",
                    "date": "2021-01-01",
                    "date_precision": "day",
                    "entity_ids": [],
                },
            ],
            schema=chunks_schema,
        ),
        tmp_path / "chunks.parquet",
    )

    qdrant_dir = tmp_path / "qdrant_db"
    cfg = RetrievalConfig(processed_dir=tmp_path, qdrant_path=qdrant_dir)
    pipeline = RetrievalPipeline(config=cfg)
    pipeline.meaning_index.build_index(force_rebuild=True, batch_size=4)

    res = pipeline.query("What is the relationship between CYP2C19 and clopidogrel?")
    by_sid = {h.source_id: h for h in res.top_evidence}

    # Unindexed PMID 999999 must never produce an item
    assert "999999" not in by_sid

    # Paper 111111 is cited on rel:pair01 where both CYP2C19 and clopidogrel resolved -> linked
    assert "111111" in by_sid
    p111 = by_sid["111111"]
    assert p111.matched_entities == ["pg:gene:124", "pg:chem:449053"]
    assert p111.provenance.get("linked_via_relationship_pmid") is True
    assert p111.provenance.get("relationship_id") == "rel:pair01"
    assert "linked_via_relationship_pmid" in p111.found_by_paths

    # Papers 222222 (other edge) and 333333 (no edge) must NEVER be linked
    for unlinked_id in ("222222", "333333"):
        if unlinked_id in by_sid:
            assert by_sid[unlinked_id].matched_entities == []
            assert not by_sid[unlinked_id].provenance.get("linked_via_relationship_pmid")
            assert "linked_via_relationship_pmid" not in by_sid[unlinked_id].found_by_paths

    pipeline.meaning_index.close()


def test_embedded_text_hash_ignores_entity_ids_and_detects_content_change(tmp_path: Path):
    """
    Verify compute_embedded_text_sha256 hashes only (chunk_id, source_type, title, content):
    - Changing entity_ids leaves the hash unchanged.
    - Changing content changes the hash.
    """
    from app.retrieval.meaning_search import compute_embedded_text_sha256

    schema = pa.schema(
        [
            ("chunk_id", pa.string()),
            ("source_type", pa.string()),
            ("source_id", pa.string()),
            ("title", pa.string()),
            ("content", pa.string()),
            ("date", pa.string()),
            ("date_precision", pa.string()),
            ("entity_ids", pa.list_(pa.string())),
        ]
    )
    base_rows = [
        {
            "chunk_id": "chunk:annotation:1",
            "source_type": "annotation",
            "source_id": "1",
            "title": "Title 1",
            "content": "Original sentence content.",
            "date": "unknown",
            "date_precision": "unknown",
            "entity_ids": ["pg:gene:124"],
        }
    ]
    p_orig = tmp_path / "orig.parquet"
    pq.write_table(pa.Table.from_pylist(base_rows, schema=schema), p_orig)
    h_orig = compute_embedded_text_sha256(p_orig)

    meta_rows = [
        {**base_rows[0], "entity_ids": ["pg:gene:124", "pg:var:166154053"], "date": "2024-01-01"}
    ]
    p_meta = tmp_path / "meta.parquet"
    pq.write_table(pa.Table.from_pylist(meta_rows, schema=schema), p_meta)
    h_meta = compute_embedded_text_sha256(p_meta)
    assert h_meta == h_orig

    content_rows = [{**base_rows[0], "content": "Modified sentence content."}]
    p_content = tmp_path / "content.parquet"
    pq.write_table(pa.Table.from_pylist(content_rows, schema=schema), p_content)
    h_content = compute_embedded_text_sha256(p_content)
    assert h_content != h_orig


def test_variant_tagging_strict_joins_and_untagged_reasons(tmp_path: Path):
    """
    Verify deterministic variant/haplotype tagging strictly from structured columns:
    - Exact rsID -> pg:var:*
    - Exact allele within row's gene (including HLA space normalization) -> pg:haplo:*
    - Phenotype labels and unknown alleles remain untagged and counted
    - Text appearing only in Sentence/Notes is NEVER mined
    - All non-entity_ids columns remain byte-identical
    """
    import zipfile

    from app.retrieval.variant_tagging import build_chunks_v2

    proc_dir = tmp_path / "processed"
    proc_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    ent_schema = pa.schema(
        [
            ("canonical_id", pa.string()),
            ("entity_type", pa.string()),
            ("primary_source_id", pa.string()),
            ("display_name", pa.string()),
            ("normalized_name", pa.string()),
            ("gene_symbol", pa.string()),
            ("is_artifact", pa.bool_()),
        ]
    )
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "canonical_id": "pg:var:166154053",
                    "entity_type": "variant",
                    "primary_source_id": "PA166154053",
                    "display_name": "rs4244285",
                    "normalized_name": "rs4244285",
                    "gene_symbol": "CYP2C19",
                    "is_artifact": False,
                },
                {
                    "canonical_id": "pg:var:999999",
                    "entity_type": "variant",
                    "primary_source_id": "PA999999",
                    "display_name": "rs777777",
                    "normalized_name": "rs777777",
                    "gene_symbol": "CYP2C19",
                    "is_artifact": False,
                },
                {
                    "canonical_id": "pg:haplo:165816542",
                    "entity_type": "haplotype",
                    "primary_source_id": "PA165816542",
                    "display_name": "CYP2C19*2",
                    "normalized_name": "cyp2c19*2",
                    "gene_symbol": "CYP2C19",
                    "is_artifact": False,
                },
                {
                    "canonical_id": "pg:haplo:165987830",
                    "entity_type": "haplotype",
                    "primary_source_id": "PA165987830",
                    "display_name": "HLA-B *57:01",
                    "normalized_name": "hla-b *57:01",
                    "gene_symbol": "HLA-B",
                    "is_artifact": False,
                },
            ],
            schema=ent_schema,
        ),
        proc_dir / "entities.parquet",
    )
    syn_schema = pa.schema(
        [
            ("canonical_id", pa.string()),
            ("synonym_text", pa.string()),
            ("normalized_synonym", pa.string()),
            ("is_artifact", pa.bool_()),
        ]
    )
    pq.write_table(pa.Table.from_pylist([], schema=syn_schema), proc_dir / "synonyms.parquet")

    # variantAnnotations.zip with 2 rows (1 matched + 1 untagged; rs777777 only in prose)
    tsv_lines = [
        "Variant Annotation ID\tVariant/Haplotypes\tGene\tDrug(s)\tSentence\tNotes",
        "101\trs4244285, CYP2C19*2\tCYP2C19\tclopidogrel\tMention of rs777777 in prose only.\t",
        "102\tPoor Metabolizer, *999\tCYP2C19\tclopidogrel\tNo rsID tagged from prose rs4244285.\t",
    ]
    with zipfile.ZipFile(raw_dir / "variantAnnotations.zip", "w") as zf:
        zf.writestr("var_drug_ann.tsv", "\n".join(tsv_lines))

    # drugLabels.zip
    dl_lines = [
        "PharmGKB ID\tName\tGenes\tVariants/Haplotypes",
        "PA111\tAbacavir label\tHLA-B\tHLA-B*57:01",
    ]
    with zipfile.ZipFile(raw_dir / "drugLabels.zip", "w") as zf:
        zf.writestr("drugLabels.tsv", "\n".join(dl_lines))

    # guidelineAnnotations.json.zip
    import json

    with zipfile.ZipFile(raw_dir / "guidelineAnnotations.json.zip", "w") as zf:
        zf.writestr(
            "PA222.json",
            json.dumps(
                {
                    "guideline": {
                        "id": "PA222",
                        "name": "CPIC Test",
                        "relatedAlleles": [{"id": "PA165816542", "symbol": "CYP2C19*2"}],
                    }
                }
            ),
        )

    chunks_schema = pa.schema(
        [
            ("chunk_id", pa.string()),
            ("source_type", pa.string()),
            ("source_id", pa.string()),
            ("title", pa.string()),
            ("content", pa.string()),
            ("date", pa.string()),
            ("date_precision", pa.string()),
            ("entity_ids", pa.list_(pa.string())),
        ]
    )
    chunks_rows = [
        {
            "chunk_id": "chunk:annotation:101",
            "source_type": "annotation",
            "source_id": "101",
            "title": "Ann 101",
            "content": "Mention of rs777777 in prose only.",
            "date": "unknown",
            "date_precision": "unknown",
            "entity_ids": ["pg:gene:124"],
        },
        {
            "chunk_id": "chunk:annotation:102",
            "source_type": "annotation",
            "source_id": "102",
            "title": "Ann 102",
            "content": "No rsID tagged from prose rs4244285.",
            "date": "unknown",
            "date_precision": "unknown",
            "entity_ids": ["pg:gene:124"],
        },
        {
            "chunk_id": "chunk:drug_label:PA111",
            "source_type": "drug_label",
            "source_id": "PA111",
            "title": "Abacavir label",
            "content": "Testing required.",
            "date": "2020-01-01",
            "date_precision": "day",
            "entity_ids": ["pg:chem:448004"],
        },
        {
            "chunk_id": "chunk:guideline:PA222",
            "source_type": "guideline",
            "source_id": "PA222",
            "title": "CPIC Test",
            "content": "Guideline body.",
            "date": "2022-01-01",
            "date_precision": "day",
            "entity_ids": ["pg:gene:124"],
        },
    ]
    pq.write_table(
        pa.Table.from_pylist(chunks_rows, schema=chunks_schema), proc_dir / "chunks.parquet"
    )

    report = build_chunks_v2(
        chunks_path=proc_dir / "chunks.parquet",
        output_path=proc_dir / "chunks_v2.parquet",
        processed_dir=proc_dir,
        clinpgx_dir=raw_dir,
    )
    assert report["non_entity_columns_byte_identical"] is True
    assert report["chunks_updated_entity_ids"] == 3
    assert report["stream_stats"]["annotation"]["untagged_token_reasons"] == {
        "phenotype_or_functional_label": 1,
        "unknown_allele": 1,
    }

    import duckdb

    con = duckdb.connect(":memory:")
    by_id = dict(
        con.execute(
            f"SELECT chunk_id, entity_ids FROM '{(proc_dir / 'chunks_v2.parquet').as_posix()}'"
        ).fetchall()
    )
    assert by_id["chunk:annotation:101"] == [
        "pg:gene:124",
        "pg:haplo:165816542",
        "pg:var:166154053",
    ]
    assert "pg:var:999999" not in by_id["chunk:annotation:101"]
    assert by_id["chunk:annotation:102"] == ["pg:gene:124"]
    assert by_id["chunk:drug_label:PA111"] == ["pg:chem:448004", "pg:haplo:165987830"]
    assert by_id["chunk:guideline:PA222"] == ["pg:gene:124", "pg:haplo:165816542"]


def test_hla_spacing_lookup_normalization_preserves_stored_names():
    """
    Verify lookup-only star-allele whitespace normalization resolves 'HLA-B*57:01'
    to stored 'HLA-B *57:01' without altering entities.parquet display_name, and q07
    resolves both HLA-B*57:01 and abacavir.
    """
    service = EntityLookupService()
    res_hla = service.lookup("HLA-B*57:01")
    assert res_hla.status == "resolved"
    assert res_hla.canonical_id == "pg:haplo:165987830"
    assert res_hla.candidates[0].display_name == "HLA-B *57:01"

    q07_res = service.extract_and_resolve_entities(
        "What adverse reaction is associated with HLA-B*57:01 and abacavir?"
    )
    q07_cids = {r.canonical_id for r in q07_res if r.canonical_id}
    assert {"pg:haplo:165987830", "pg:chem:448004"}.issubset(q07_cids)





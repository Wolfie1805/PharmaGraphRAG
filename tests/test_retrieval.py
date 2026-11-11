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



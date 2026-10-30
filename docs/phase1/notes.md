# Phase 1 Architectural Boundary & Deferred Work Notes

## Scope Boundary
Phase 1 is strictly restricted to **raw data acquisition, immutable storage, run manifests, license records, and DVC tracking**.

## Explicit Out-of-Scope Items (Deferred to Subsequent Phases)
The following operations are intentionally deferred and will not be implemented in Phase 1:
1. **Schema Parsing & Transformation:** Raw files are saved byte-for-byte in `data/raw/<source>/<date>_<run_id>/`. No conversion of TSV, JSON, or PubMed XML into internal domain models.
2. **Normalization & Canonical IDs:** Gene symbol normalization (e.g., HGNC), drug naming (RxNorm, ATC), and variant normalization (dbSNP RSIDs) belong to Phase 3.
3. **Entity Resolution:** Biomedical entity linking and disambiguation belong to Phase 3.
4. **Database Ingestion:** No database loading into PostgreSQL (relational metadata), Neo4j (Knowledge Graph), or Qdrant (vector index).
5. **Text Chunking & Embeddings:** Biomedical sentence splitting, chunking, tokenization, dense embedding generation, and sparse BM25 indexing belong to Phases 5 & 6.
6. **LLM Calls & Prompting:** Grounded prompt construction and LLM inference belong to Phase 9.
7. **Secondary Data Sources:** ChEMBL (bioactivity/targets), openFDA (drug labeling), and DrugCentral (structure/interactions) will be acquired in Phase 2 / enrichment phases.
8. **Application Interfaces:** FastAPI endpoints (Phase 11) and React UI (Phase 11).

## Phase 0 Items Deferred
The following Phase 0 skeleton items are intentionally deferred per user instruction and will be completed in a separate step before Phase 3:
1. `docker-compose.yml` (PostgreSQL, Neo4j, Qdrant containers).
2. Root `README.md` (high-level system documentation across all phases).
3. Remaining empty application and graph skeleton directories from PharmaRAG.md section 12:
   - `app/api/`
   - `app/normalization/`
   - `app/entities/`
   - `app/graph/`
   - `app/retrieval/` (sparse, dense, graph, fusion, reranking)
   - `app/evidence/`
   - `app/generation/`
   - `app/evaluation/`
   - `graph/schema/`
   - `graph/seed/`
   - `experiments/`
   - `notebooks/`
   - `docker/`
   - `frontend/`

## Observations from Source Verification (2026-10-30)
- **ClinPGx File Hosting:** Served as direct static zip attachments from Cloudflare/AWS S3 via `https://api.clinpgx.org/v1/download/file/data/<fileName>`. No login or interactive auth required.
- **PubMed E-utilities:** Windows OpenSSL CA bundle in vanilla Python 3.12 without `certifi` fails on NCBI's GoDaddy intermediate certificate. Python client must use `certifi` or `truststore` (or `httpx` with bundled CAs).
- **NCBI Request Rate:** Strict limits (2 req/s safe default without key, 8 req/s with key).


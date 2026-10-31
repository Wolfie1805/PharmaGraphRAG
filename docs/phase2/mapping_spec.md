# Phase 2: Data Mapping & Normalization Specification (Revised)

> **Notice**: Updated pursuant to Task 1 review. Incorporates measured empirical findings from raw ClinPGx archives and PubMed XML.

---

## 1. Core Principles & Non-Negotiable Constraints

1. **Raw Immutability**: All files under `data/raw/` are strictly read-only. No unzipping or modification occurs under `data/raw/`.
2. **Deterministic Processing**: Identical raw inputs and config produce byte-identical Parquet files. Records are sorted by canonical ID / primary key before serialization. No timestamps are stored inside data rows (timestamps reside solely in manifests).
3. **No Inferred Mappings**: Cross-references and entity links exist only if explicitly asserted in source files. **No star-allele to rsID relationships exist in the selected Phase 1 raw data**, and none will be inferred.
4. **No Silent Loss ($\text{raw\_rows} = \text{accepted} + \text{rejected}$)**:
   - Default rejection abort threshold is strictly **0.1% per file** (reduced from 2.0%).
   - If any input file exceeds 0.1% rejected rows, the process halts immediately.
   - For structured TSV files, any rejection at all is logged to `<file>.rejects.jsonl` and surfaced in the run manifest.
5. **Categorized Rejection Reasons**:
   - `EMPTY_PRIMARY_ID`: Missing or blank accession/identifier.
   - `DELIMITER_CORRUPTION`: Mismatched column count or corrupted quoting.
   - `FIELD_OVERFLOW`: Field length exceeds the 250,000-byte safety limit.
   - `UNPARSEABLE_RECORD`: Corrupted JSON payload or unparseable XML node.
6. **Provenance on Every Record**: Every record preserves:
   - `source_name`: String (`"ClinPGx"` or `"PubMed"`).
   - `raw_file_path`: Path relative to workspace (e.g. `data/raw/clinpgx/20261030_79ff97e7/drugs.zip#drugs.tsv`).
   - `raw_file_sha256`: SHA-256 of the parent raw archive.
   - `raw_manifest_run_id`: Run ID from Phase 1 manifest.
   - `record_index`: 1-based integer line number or XML node index.

---

## 2. Entity Identity & Deduplication Policy

### 2.1 ClinPGx PharmGKB Accession Unification
Empirical profiling established that:
- `drugs.tsv` contains 3,770 accessions.
- `chemicals.tsv` contains 5,329 accessions.
- Exactly 3,770 accessions are shared between both files. `drugs.tsv` is a 100% strict subset of `chemicals.tsv`.
- There are **0 name collisions** under different accessions.

**Resolution Policy**:
- A PharmGKB Accession ID (`PA...`) defines a single canonical chemical/compound entity in the registry (`pg:chem:<number>`).
- Drug status is represented as an attribute (`is_drug: bool`), **never as a second canonical entity**.
- In the entity registry, the primary source key is `(chemical, "PA...")`.
- If the same display name ever appears under differing accession IDs, it is **NOT** merged automatically. It is written to `data/review/duplicate_candidates.jsonl` with evidence for human review.

### 2.2 Canonical ID Assignment & Stable Registry
- Format: `pg:<type>:<zero_padded_number>` (e.g., `pg:gene:000001`, `pg:chem:000042`, `pg:var:000100`).
- **Registry File**: `data/entity_registry.jsonl` (committed to git, append-only, private).
- **Format**: One JSON record per line, sorted by `canonical_id`, preceded by a schema header:
  ```json
  {"_header": true, "schema_version": "1.0", "entity_count": 34262, "last_updated_utc": "2026-10-31T12:00:00Z"}
  {"canonical_id": "pg:chem:000001", "entity_type": "chemical", "primary_source_id": "PA448053", "display_name": "clopidogrel", "is_drug": true, "status": "active"}
  ```
- **Rebuild Rule**: Subsequent runs must load existing IDs from `data/entity_registry.jsonl`, reuse existing mappings, and append new entities at the end. Renumbering or ID reassignment is strictly prohibited.
- **Git Tracking**: Exception added to `.gitignore` (`!data/entity_registry.jsonl`) to ensure it is committed to git and excluded from DVC raw ignores.

---

## 3. Data Contracts & Model Specifications

### 3.1 `Entity`
- `canonical_id`: String (`pg:<type>:<number>`)
- `entity_type`: Literal string (`"gene"`, `"chemical"`, `"variant"`)
- `primary_source_id`: Source ID (e.g. `"PA267"`, `"PA449088"`, `"rs4244285"`)
- `display_name`: Verbatim casing from source
- `normalized_name`: Unicode normalized (NFKC), punctuation-unified, case-folded string for lookup
- `is_drug`: Boolean flag (true if entity appears in `drugs.tsv`)
- `provenance`: Provenance metadata object

### 3.2 `CrossReference`
- `canonical_id`: Reference to `Entity.canonical_id`
- `namespace`: External authority (`"NCBI_GENE"`, `"ENSEMBL"`, `"HGNC"`, `"DRUGBANK"`, `"RXNORM"`, `"PUBCHEM_COMPOUND"`, `"DBSNP"`, `"UMLS"`, `"CHEBI"`, `"UNIPROT"`, `"ATC"`)
- `external_id`: External identifier string
- `provenance`: Provenance metadata object

### 3.3 `Synonym`
- `canonical_id`: Reference to `Entity.canonical_id`
- `synonym_text`: Raw synonym string
- `normalized_synonym`: Normalized search key (NFKC, case-folded, stripped)
- `synonym_type`: Category (`"trade_name"`, `"generic_name"`, `"symbol_alias"`, `"alternate_name"`, `"brand_mixture"`)
- `is_split_ambiguous`: Boolean flag (true if comma occurred inside quotes/parentheses)
- `provenance`: Provenance metadata object

### 3.4 `Publication` (PubMed Specification)
- `pmid`: String of digits only (`r'^\d+$'`)
- `record_type`: Literal string (`"PubmedArticle"` or `"PubmedBookArticle"`)
- `title`: Normalized article or book chapter title
- `journal_or_book`: Journal name or Book Title (e.g. `"Medical Genetics Summaries"`)
- `pubdate_year_raw`: Raw year string from XML
- `pubdate_month_raw`: Raw month string if present (or `None`)
- `pubdate_day_raw`: Raw day string if present (or `None`)
- `pubdate_season_raw`: Raw season string if present (or `None`)
- `pubdate_medline_raw`: Raw MedlineDate string if present (or `None`)
- `pubdate_iso`: Normalized ISO date (`YYYY`, `YYYY-MM`, or `YYYY-MM-DD`). For season dates, precision is `"year"` only, and month/day remain `None`. Seasons are **never** mapped to arbitrary months.
- `date_precision`: Literal string (`"day"`, `"month"`, or `"year"`)
- `doi`: Normalized DOI string if present (or `None`)
- `book_accession`: NCBI Bookshelf accession ID if present (or `None`)
- `abstract_text`: Full abstract text string (unstructured or concatenated)
- `abstract_structured`: Boolean flag
- `abstract_sections`: List of `{"label": "METHODS", "text": "..."}` dicts preserving structured section headers
- `mesh_terms`: List of MeSH Descriptor strings
- `publication_types`: List of publication type tags
- `provenance`: Provenance metadata object

### 3.5 `AnnotationRecord`
- `annotation_id`: Source accession / identifier
- `annotation_type`: Literal string (`"clinical_variant"`, `"variant_drug"`, `"variant_phenotype"`, `"drug_label"`, `"guideline"`, `"summary"`)
- `gene_symbol`: Gene symbol if present
- `drug_name`: Drug or chemical name if present
- `variant_name`: Variant or star-allele string
- `level_of_evidence`: ClinPGx Level of Evidence string
- `pmids`: List of cited PMIDs extracted directly from the record
- `raw_fields`: Dict storing all original TSV columns untouched
- `provenance`: Provenance metadata object

---

## 4. Multi-Value Field Handling & CSV Limits

1. **Parser CSV Field Limit**:
   - Limit set to **250,000 bytes** (250 KB) across all TSV readers.
   - If any cell length exceeds 250,000 bytes, processing fails immediately with `FieldSizeLimitExceededError`.
2. **List-Valued Fields**:
   - For every multi-value column, the schema retains:
     1. The unmodified raw string (e.g. `raw_trade_names: str`).
     2. The parsed, trimmed list of elements (e.g. `trade_names: list[str]`).
   - Comma splitting rules:
     - If quotes (`"..."`) or parentheses (`(...)`) enclose commas (e.g. `"UK-148,993"` or `Zovirax Injection (Zovirax sodium)`), the parser uses a regex/quote-aware tokenizer.
     - Ambiguous cases are marked with `is_split_ambiguous = True` and surfaced in the review log.

---

## 5. `relationships.tsv` & Dangling Reference Accounting

- Total rows: **246,714**.
- Relationships connect registered entities (`Gene`, `Chemical`, `Variant`) to each other as well as unmodeled entities (`Phenotype`, `Disease`, `Haplotype`).
- **Policy**:
  - If both `Entity1` and `Entity2` map to the entity registry, their canonical IDs are recorded in `entity1_canonical_id` and `entity2_canonical_id`.
  - If either endpoint is not in the entity registry (e.g. `Phenotype:PA447214`), the row is **kept**, marked `is_dangling = True`, with the unmapped endpoint retained in `raw_entity_id`.
  - Zero relationship rows are discarded. Dangling counts are reported in the processed manifest.

---

## 6. Target Directory Layout

All outputs will be generated as sorted, deterministic Parquet files under `data/processed/<source>/<run_id>/`:
```
data/
  entity_registry.jsonl            # Committed to git, stable append-only registry
  processed/
    clinpgx/
      <run_id>/
        entities.parquet           # Genes, Chemicals, Variants
        cross_references.parquet   # External database IDs (NCBI, Ensembl, DrugBank, etc.)
        synonyms.parquet           # Trade names, aliases, brand mixtures
        annotations.parquet        # Clinical and guideline annotations
        relationships.parquet      # Entity-to-entity relations with dangling flags
        rejects/                   # Rejected rows with categorized reasons
          <source_file>.rejects.jsonl
    pubmed/
      <run_id>/
        publications.parquet       # Articles & Book Articles with structured abstracts
        publication_mesh.parquet   # MeSH headings
        rejects/
          pubmed.rejects.jsonl
```

---

## 7. Proposed New Dependencies for Phase 2

Before installing, these dependencies are proposed for user approval:

| Package | Pinned Version | Purpose & Justification |
| :--- | :--- | :--- |
| `pyarrow` | `19.0.1` | Fast, deterministic read/write of Parquet tables under `data/processed/` with strict schema validation. |
| `hypothesis` | `6.128.0` | Property-based testing framework to rigorously prove normalization idempotence: $\forall x, \text{norm}(\text{norm}(x)) == \text{norm}(x)$. |

No other dependencies are required. All other tasks utilize standard Python libraries (`csv`, `xml.etree`, `zipfile`, `json`, `pathlib`) and existing project dependencies (`pydantic`, `pytest`, `ruff`).

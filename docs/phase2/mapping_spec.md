# Phase 2: Data Mapping & Normalization Specification (Final Spec)

> **Status**: Comprehensive update incorporating all Task 1 empirical measurements, full PubMed corpus (3,096 records), and CPIC/ClinPGx haplotype definitions.
> **Constraint**: DO NOT write parsers or contracts until this specification is explicitly confirmed.

---

## 1. Core Principles & Non-Negotiable Operational Constraints

1. **Raw Immutability**: All data under `data/raw/` is write-once, immutable, and strictly read-only. No raw archives are unzipped or altered on disk.
2. **Determinism**: Identical raw inputs and config must produce byte-identical Parquet files:
   - **Parquet Writer Settings**: `engine="pyarrow"`, `compression="SNAPPY"`, `row_group_size=50000`.
   - **Sorting**: All output tables are deterministically sorted by their primary key / canonical ID prior to serialization.
   - **Timestamps**: No internal record-generation timestamps (`created_at`, `extracted_at`) exist inside Parquet data columns. Run timestamps reside exclusively in the external output manifests.
   - **Schemas**: Explicit PyArrow schemas are enforced (no automatic type inference).
3. **No Inferred Mappings**: Mappings and entity links exist only if explicitly asserted in source columns.
   - **Zero files define star-allele to rsID relationships.** No inferred star-allele to rsID relationships will be constructed.
4. **No Silent Loss ($\text{raw\_rows} = \text{accepted} + \text{rejected}$)**:
   - Default rejection abort threshold is strictly **0.1% per file**.
   - If any input file exceeds 0.1% rejected records, parsing halts immediately with an abort exception.
   - For all structured TSV files, any rejection at all is logged to `<output_table>.rejects.jsonl` with an explicit categorized reason.
5. **Categorized Rejection Reasons**:
   - `EMPTY_PRIMARY_ID`: Missing or blank primary identifier/accession.
   - `DELIMITER_CORRUPTION`: Mismatched column count or malformed quoting.
   - `FIELD_OVERFLOW`: Field length exceeds the 250,000-character safety limit.
   - `UNPARSEABLE_RECORD`: Malformed JSON or unparseable XML node.
   - `PILOT_MANIFEST_REJECTED`: Ingestion attempted on an archived pilot manifest when full corpus is required.
6. **CSV Character Field Limit**:
   - Python's `csv.field_size_limit()` counts **characters**, not bytes.
   - Limit is set to **250,000 characters** (measured max across corpus is 148,743 characters in `Brand Mixtures`; this provides a ~68% safety margin while preventing memory exhaustion on runaway corrupt lines).
7. **Multi-Value Field Parsing & Source Artifacts**:
   - Fields containing delimited lists (`Trade Names`, `Alternate Names`) must be parsed via `csv.reader(..., skipinitialspace=True)` to preserve quoted multi-word strings and compound codes (e.g. `"UK-148,993"`, `"Benzoic acid, benzyl ester"`).
   - In `drugs.tsv` and `chemicals.tsv`, exactly **48 rows** contain commas together with quotes or parentheses (34 with quotes, 14 with parentheses).
   - Parenthetical commas: Quote-aware parsing does NOT protect commas inside parentheses. In 13 rows, parentheses are single-item qualifiers (`Zovirax Injection (Zovirax sodium)`). In 1 row (`PA164743704`, antithymocyte globulin), parenthetical commas are unbalanced in source text.
   - Malformed artifacts (`PA449283` Diazepam `'Faustan,'`, `PA164743704` Antithymocyte globulin `'Genzyme)'` and `'Thymoglobulin (SangStat Medical'`) are kept verbatim in raw data, flagged with `is_artifact = True`, and excluded from resolver synonyms.
8. **PubMed Ingestion Scope & Version Locking**:
   - The PubMed parser will strictly reject pilot manifests (`is_pilot == true`).
   - It will consume only the verified full corpus manifest: `manifest_pubmed_20261031_7d1398e0.json` (3,096 records across 16 XML files).
   - Both `<PubmedArticle>` (3,085) and `<PubmedBookArticle>` (11) must be parsed into the unified publication contract.

---

## 2. Entity Registry, Identity & Deduplication Policy

### 2.1 ClinPGx PharmGKB Accession Unification
Empirical profiling established:
- `drugs.tsv` (3,770 accessions) is a 100% strict subset of `chemicals.tsv` (5,329 accessions).
- Accessions in both: 3,770. Only in chemicals: 1,559. Only in drugs: 0.
- Primary name collisions under differing accessions: 0.

**Identity Rules**:
- A PharmGKB Accession ID (`PA...`) represents a single canonical compound entity in the registry (`pg:chem:<number>`).
- Drug classification is represented as an attribute (`is_drug: bool`), **never as a second canonical entity or secondary ID**.
- Primary source key in registry: `(chemical, "PA...")`.

### 2.2 Synonym, Cross-Entity & Ambiguous Surface Form Collisions
1. **Intra-Chemical Collisions**: Profiling revealed **76 distinct surface forms** (69 trade names, 7 alternate names) that map to multiple distinct chemical accessions (e.g. `desoxyn` -> methamphetamine, dextroamphetamine, amphetamine; `darvocet` -> acetaminophen, acetaminophen / propoxyphene napsylate).
2. **Cross-Entity Collisions (Gene vs Chemical)**: Case-folding gene symbols and names against chemical names and synonyms revealed **26 cross-entity collisions** (e.g. `ADM`, `APC`, `asparaginase`, `AVIL`, `coagulation factor IX`, `CP`, `CYREN`, `DBH`, `DBI`, `erythropoietin`).
3. **Source Quirks Recorded as Facts**: Ambiguous source assertions, such as `"doxil"` mapping to both `PA164750492` (almitrine) and `PA449412` (doxorubicin), are recorded as source facts, flagged with `is_ambiguous = True`, without artificial correction.

**Collision Rules**:
- Ambiguous surface forms are **never** auto-merged into a canonical entity.
- The entity resolver remains strictly type-aware.
- Colliding instances are cataloged in `data/review/ambiguous_synonyms.jsonl` (intra-chemical) and `data/review/cross_entity_collisions.jsonl` (cross-entity).

### 2.3 Star Alleles & Haplotypes Modeling
- **Entities**: Modeled as canonical entities `pg:haplo:<number>` sourced from `clinpgxHaplotypes_star_alleles.tsv` (485 alleles), `clinpgxHaplotypes_named_alleles.tsv` (758 alleles), and `cpic.alleles.json` (3,813 alleles across 22 pharmacogenes).
- **Attributes**:
  - `accession_id`: PharmGKB Accession ID (e.g. `PA165818750`).
  - `gene_symbol`: Pharmacogene symbol (e.g. `CYP2B6`, `CYP2C19`).
  - `allele_name`: Star allele or named allele (e.g. `*1`, `*2`, `*4`).
  - `hgvs`: RefSeq genomic HGVS string if provided (e.g. `NG_007929.1:g.5071C>T`).
  - `structural_variation`: Structural variation description if provided.
  - `amp_level`: AMP tier level if classified.
- **Relational Boundary**: Because zero source files explicitly map star alleles to rsIDs, **zero inferred variant links are generated**.
- **Free-Text Rule**: Named alleles such as `"rs2231142 reference (G)"` contain rsID strings embedded in free-text names. In accordance with project rules, **zero rsIDs will be extracted or parsed from allele names or any other free text**. The name is preserved exactly as given.

### 2.4 Canonical ID Assignment & Git-Tracked Registry
- **ID Formatting**:
  - Genes: `pg:gene:<06d>` (e.g., `pg:gene:000001` through `pg:gene:025041`)
  - Chemicals/Drugs: `pg:chem:<06d>` (e.g., `pg:chem:000001` through `pg:chem:005329`)
  - Variants: `pg:var:<06d>` (e.g., `pg:var:000001` through `pg:var:007692`)
  - Haplotypes/Alleles: `pg:haplo:<06d>`
  - Unmodeled Relationship Endpoints: `pg:snv:<06d>`, `pg:pheno:<06d>`, `pg:cnv:<06d>`
- **Registry Persistence**: `data/entity_registry.jsonl`.
- **Git Tracking & DVC Isolation**:
  - `data/entity_registry.jsonl` is explicitly un-ignored in `.gitignore` (`!data/entity_registry.jsonl`) and committed to Git.
  - Verified via `git check-ignore -v data/entity_registry.jsonl` (`.gitignore:24:!data/entity_registry.jsonl`).
  - It is outside `data/processed/` and `data/raw/`, and is completely outside DVC.
- **Rebuild Rule**: Subsequent runs load existing entries from `data/entity_registry.jsonl` and append new entities. Renumbering or reassigning existing IDs is strictly prohibited.

### 2.5 Dangling Relationship Endpoints Architecture (Section B.1 & B.2)
1. **Decision (Section B.1)**:
   - For endpoint types not defined by any dedicated file (`Phenotype`, `SNV`, `GeneCopyNumberVariation`, and unlisted `StarAllele`, `HlaAllele`, `Haplotype`, and `Variant` endpoints), entities are created directly from `relationships.tsv` using the `id`, `name`, and `type` the file itself provides.
   - Assigned attribute: `defined_by = "relationships_only"`, with full provenance.
   - Type label kept exactly as the source states (zero subclassification).
   - In `relationships.parquet`, all edges connecting `relationships_only` endpoints are flagged with `is_dangling = True`.
2. **Investigation & Proposal for SNV Endpoints (Section B.2)**:
   - SNV endpoint IDs (`PA1663...`) have 0 matches in `variants.tsv` `Variant ID`.
   - SNV endpoint Names are genomic HGVS coordinate strings.
   - Testing an exact string join against individual tokens in `variants.tsv` `Synonyms`:
     - **1,694 SNV Names** match an exact synonym token in `variants.tsv`.
     - **11,664 SNV Names** do not match (they use reference allele `=` notation or legacy gene-centric coordinates).
   - **Proposal**: These 1,694 exact source-stated matches are logged to `data/review/snv_variant_exact_matches.jsonl` as candidate links, but the SNV entities remain distinct from `pg:var:` rsID variants until explicit approval.

---

## 3. Data Contracts & Output Schema Specifications

All tabular outputs will be written to `data/processed/` as Snappy-compressed Parquet files, with rejects in JSONL format.

### 3.1 Entity Table (`entities.parquet`)
| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `canonical_id` | `string` | No | Stable internal identifier (`pg:<type>:<number>`) |
| `entity_type` | `string` | No | `"gene"`, `"chemical"`, `"variant"`, `"haplotype"` |
| `primary_source_id` | `string` | No | Primary identifier (`PA...`, `rs...`) |
| `display_name` | `string` | No | Verbatim official display name from source |
| `normalized_name` | `string` | No | NFKC normalized, punctuation-unified, case-folded name |
| `is_drug` | `bool` | No | True if chemical is classified as a drug in `drugs.tsv` |
| `gene_symbol` | `string` | Yes | Applicable to genes and haplotypes |
| `source_name` | `string` | No | `"ClinPGx"` or `"CPIC"` |
| `raw_file_sha256` | `string` | No | SHA-256 of the source raw archive |
| `raw_manifest_run_id`| `string` | No | Manifest run ID |

### 3.2 Cross-Reference Table (`cross_references.parquet`)
| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `canonical_id` | `string` | No | Reference to `entities.canonical_id` |
| `namespace` | `string` | No | External authority (`NCBI_GENE`, `ENSEMBL`, `HGNC`, `DRUGBANK`, `RXNORM`, `PUBCHEM_COMPOUND`, `DBSNP`, `UMLS`, `CHEBI`, `UNIPROT`, `ATC`) |
| `external_id` | `string` | No | External accession or identifier |
| `raw_file_sha256` | `string` | No | SHA-256 of the source archive |

### 3.3 Synonym Table (`synonyms.parquet`)
| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `canonical_id` | `string` | No | Reference to `entities.canonical_id` |
| `synonym_text` | `string` | No | Verbatim synonym or trade name |
| `normalized_synonym`| `string` | No | NFKC normalized, case-folded search string |
| `synonym_type` | `string` | No | `"trade_name"`, `"generic_name"`, `"symbol_alias"`, `"alternate_name"`, `"brand_mixture"` |
| `is_ambiguous` | `bool` | No | True if surface form maps to multiple canonical entities |
| `raw_file_sha256` | `string` | No | SHA-256 of the source archive |

### 3.4 Relationship Table (`relationships.parquet`)
| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `relationship_id` | `string` | No | Deterministic hash ID `rel:<md5(entity1+entity2+assoc)>` |
| `entity1_canonical_id`| `string`| Yes | Canonical ID if resolved in registry, else `None` |
| `entity1_source_id` | `string` | No | Source ID (`Entity1_id`) |
| `entity1_source_name`| `string` | No | Source display name (`Entity1_name`) |
| `entity1_type` | `string` | No | Raw type (`Chemical`, `Gene`, `Variant`, `SNV`, `Phenotype`, etc.) |
| `entity2_canonical_id`| `string`| Yes | Canonical ID if resolved in registry, else `None` |
| `entity2_source_id` | `string` | No | Source ID (`Entity2_id`) |
| `entity2_source_name`| `string` | No | Source display name (`Entity2_name`) |
| `entity2_type` | `string` | No | Raw type |
| `association` | `string` | No | Verbatim relationship type (`associated`, `not associated`) |
| `pmids` | `list<string>`| No | List of supporting PMIDs |
| `is_dangling` | `bool` | No | True if either endpoint lacks a canonical entity in the registry |
| `raw_file_sha256` | `string` | No | SHA-256 of the source archive |

### 3.5 Publication Table (`publications.parquet`)
| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `pmid` | `string` | No | Digits-only PubMed ID |
| `record_type` | `string` | No | `"PubmedArticle"` or `"PubmedBookArticle"` |
| `title` | `string` | No | Normalized article or book chapter title |
| `journal_or_book` | `string` | No | Journal title or Bookshelf title (*Medical Genetics Summaries*) |
| `pubdate_iso` | `string` | No | Normalized ISO date (`YYYY`, `YYYY-MM`, or `YYYY-MM-DD`) |
| `date_precision` | `string` | No | `"year"`, `"month"`, or `"day"` |
| `pubdate_raw_year` | `string` | Yes | Raw XML Year |
| `pubdate_raw_month`| `string` | Yes | Raw XML Month (or `None`) |
| `pubdate_raw_day` | `string` | Yes | Raw XML Day (or `None`) |
| `pubdate_raw_medline`| `string`| Yes | Raw XML MedlineDate (or `None`) |
| `doi` | `string` | Yes | DOI string if present in article IDs |
| `book_accession` | `string` | Yes | Bookshelf accession (e.g. `NBK65798`) for BookArticles |
| `abstract_text` | `string` | No | Full concatenated abstract string |
| `abstract_structured`| `bool` | No | True if abstract contains structured sections |
| `abstract_sections`| `string` (JSON)| Yes | JSON list of `[{"label": "METHODS", "text": "..."}]` |
| `mesh_terms` | `list<string>`| No | List of MeSH Descriptor names (empty for books/pre-indexed) |
| `raw_file_sha256` | `string` | No | SHA-256 of the XML batch file |

---

## 4. Rejection & Human Review Artifacts

Every parser run emits structured review and audit artifacts:
1. `data/review/ambiguous_synonyms.jsonl`: Catalog of the 76 colliding surface forms mapping to multiple chemical accessions.
2. `data/review/unlinked_relationships.jsonl`: Detailed inventory of the 191,466 relationship rows where one or both endpoints represent unmodeled entity types (`SNV`, `Phenotype`, `GeneCopyNumberVariation`).
3. `data/processed/<table_name>.rejects.jsonl`: Strict log of any rejected record with verbatim content and categorized rejection code.

---

## 5. Verification & Testing Requirements

Before code execution in Task 2:
1. **Property-Based Testing (Hypothesis)**:
   - Roundtrip normalization tests on chemical names and synonyms.
   - Date parser property test: fuzz with arbitrary combinations of XML year, month, day, MedlineDate, and season strings. Verify that seasons are never mapped to arbitrary calendar months.
   - Quote-aware multi-value splitter test: verify that quoted commas are never split.
2. **Deterministic Parquet Equality Test**:
   - Parse and write sample subsets twice in memory, verify that PyArrow produces 100% byte-identical outputs.
3. **Pydantic Model Validation**:
   - Pydantic models for all entities and publications, ensuring strict typing, non-nullable constraints, and provenance tracking.

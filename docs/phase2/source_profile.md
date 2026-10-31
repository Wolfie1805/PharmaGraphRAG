# Phase 2: Source Data Profile (Measured & Verified)

> **Notice**: Measured deterministically from in-memory inspection of Phase 1 raw data (`data/raw/clinpgx/20261030_79ff97e7/` and `data/raw/pubmed/20261030_9a48695d/`).
> No raw files were extracted or modified on disk.

---

## 1. Executive Summary & Raw Catalog Inventory

| Source Archive | Contained Stream / File | Format | Total Rows / Records | Encoding | Delimiter | Max Field Length (Bytes) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `genes.zip` | `genes.tsv` | TSV | **25,041** | UTF-8 | Tab (`\t`) | 1,808 |
| `drugs.zip` | `drugs.tsv` | TSV | **3,770** | UTF-8 | Tab (`\t`) | 148,743 |
| `chemicals.zip` | `chemicals.tsv` | TSV | **5,329** | UTF-8 | Tab (`\t`) | 148,743 |
| `variants.zip` | `variants.tsv` | TSV | **7,692** | UTF-8 | Tab (`\t`) | 14,181 |
| `clinicalVariants.zip` | `clinicalVariants.tsv` | TSV | **5,192** | UTF-8 | Tab (`\t`) | 447 |
| `drugLabels.zip` | `drugLabels.tsv` | TSV | **1,435** | UTF-8 | Tab (`\t`) | 1,118 |
| `drugLabels.zip` | `drugLabels.byGene.tsv` | TSV | **239** | UTF-8 | Tab (`\t`) | 11,108 |
| `summaryAnnotations.zip`| `summary_annotations.tsv` | TSV | **5,192** | UTF-8 | Tab (`\t`) | 447 |
| `summaryAnnotations.zip`| `summary_ann_alleles.tsv` | TSV | **16,122** | UTF-8 | Tab (`\t`) | 1,364 |
| `summaryAnnotations.zip`| `summary_ann_history.tsv` | TSV | **14,056** | UTF-8 | Tab (`\t`) | 436 |
| `summaryAnnotations.zip`| `summary_ann_evidence.tsv` | TSV | **15,542** | UTF-8 | Tab (`\t`) | 530 |
| `variantAnnotations.zip`| `var_drug_ann.tsv` | TSV | **13,030** | UTF-8 | Tab (`\t`) | 2,402 |
| `variantAnnotations.zip`| `var_pheno_ann.tsv` | TSV | **14,570** | UTF-8 | Tab (`\t`) | 1,816 |
| `variantAnnotations.zip`| `var_fa_ann.tsv` | TSV | **2,189** | UTF-8 | Tab (`\t`) | 1,481 |
| `variantAnnotations.zip`| `study_parameters.tsv` | TSV | **36,083** | UTF-8 | Tab (`\t`) | 777 |
| `relationships.zip` | `relationships.tsv` | TSV | **246,714** | UTF-8 | Tab (`\t`) | 3,239 |
| `guidelineAnnotations.json.zip`| 219 JSON files | JSON | **219** | UTF-8 | JSON | N/A |
| `pubmed (pilot XML)` | `batch_0001.xml` | XML | **41** | UTF-8 | XML | N/A |

---

## 2. In-Depth Profiling Findings

### 2.1 Identity: `drugs.tsv` vs `chemicals.tsv`
- **Total `drugs.tsv` Accessions**: 3,770
- **Total `chemicals.tsv` Accessions**: 5,329
- **Accessions in Both**: **3,770** (100.0% of `drugs.tsv` accessions exist in `chemicals.tsv`)
- **Only in `drugs.tsv`**: **0**
- **Only in `chemicals.tsv`**: **1,559** (chemicals that are metabolites, environmental agents, or experimental molecules)
- **Name Collisions**: **0** (no instances of identical names mapping to distinct accession IDs).
- **Architectural Conclusion**: A PharmGKB accession (`PA...`) defines a single canonical chemical entity. Drug status is an attribute (`is_drug = True`), not a separate canonical entity or ID.

### 2.2 Maximum Field Lengths & CSV Limits
- Default Python CSV limit is 128 KB (131,072 bytes).
- Measured maximum field length across all files: **148,743 bytes** (Column `Brand Mixtures` in `drugs.tsv` and `chemicals.tsv`).
- Next longest field: 14,181 bytes (`Synonyms` in `variants.tsv`).
- **Rule**: Set CSV field limit to **250,000 bytes** (observed max + 101,257 bytes margin). Parser will raise `FieldSizeLimitExceededError` loudly if any field exceeds 250,000 bytes. Do not use 2 GB.

### 2.3 Star Alleles & Haplotype Definition Analysis
- In `variants.tsv`: All 7,692 rows are `rsID` single nucleotide variants. Zero rows represent star alleles (`*2`, `*3`, etc.).
- In `relationships.tsv`: Zero rows link a star allele directly to an rsID.
- In `clinicalVariants.tsv` & `summary_annotations.tsv`: Star alleles appear as strings in annotation context (e.g. `CYP2C19*2`, `VKORC1 -1639G>A`).
- **Catalog Finding**: The ClinPGx catalog contains separate dedicated haplotype/allele archives that were **not** part of the Phase 1 download selection:
  - `clinpgxHaplotypes.zip`
  - `haplotypes.zip`
  - `cpic.alleles.csv` / `cpic.alleles.json`
  - `pharmgkb_haplotype_frequencies_UKBB.zip`
  - `pharmgkb_haplotype_frequencies_AllOfUs.zip`
- **Rule**: **No selected file defines star-allele to rsID relationships.** No inferred star-allele to rsID mapping will be constructed.

### 2.4 Multi-Value Field Separator Ambiguity
- `Trade Names` in `drugs.tsv`: Comma-separated. Exactly 48 rows contain internal quotes or parenthetical specifications (e.g. `"UK-148,993", "UK-148993"`, `Zovirax Injection (Zovirax sodium)`).
- **Rule**: For all multi-value fields, keep the unparsed raw string AND the parsed list. When commas occur inside quotes or parentheses, mark `is_split_ambiguous = True` and retain the un-split raw token for review.

### 2.5 `relationships.tsv` Endpoints & Dangling Relationships
- Total Relationship Rows: **246,714**
- Top Endpoint Types:
  - `SNV -> Chemical` / `Chemical -> SNV`: 62,770
  - `SNV -> Phenotype` / `Phenotype -> SNV`: 59,340
  - `Variant -> Chemical` / `Chemical -> Variant`: 34,092
  - `Variant -> Phenotype` / `Phenotype -> Variant`: 31,868
  - `Gene -> Chemical` / `Chemical -> Gene`: 20,850
- Endpoint Coverage against Registered Entities (`genes`, `drugs`, `chemicals`, `variants`):
  - `Entity1` not in registry: 61,956 rows
  - `Entity2` not in registry: 61,956 rows
  - Both endpoints not in registry: 67,554 rows
  - Total Dangling Rows: **191,466 rows** (77.6% of relationships involve unmodeled entities such as Diseases, Phenotypes, and Haplotypes).
- **Rule**: Dangling relationships are preserved, flagged with `is_dangling = True`, with the raw endpoint IDs kept intact. Zero rows dropped silently.

---

## 3. PubMed Status & Profile (Pilot)

- **Raw Directories under `data/raw/pubmed/`**: Exactly 1 directory (`20261030_9a48695d`).
- **Manifest Run Type**: `is_pilot = true` (`manifest_pubmed_20261030_9a48695d.json`).
- **Query Breakdown**:
  - `CYP2C19_clopidogrel`: 13 pilot PMIDs selected (from 1,431 total)
  - `CYP2C9_warfarin`: 13 pilot PMIDs selected (from 1,409 total)
  - `VKORC1_warfarin`: 13 pilot PMIDs selected (from 978 total)
  - `SLCO1B1_simvastatin`: 13 pilot PMIDs selected (from 141 total)
- **Requested vs Received & Deduplication**:
  - 13 PMIDs × 4 pairs = 52 query candidate slots.
  - 11 slots overlapped between warfarin pairs (`CYP2C9` and `VKORC1`), yielding **41 unique PMIDs**.
  - Exactly 41 PMIDs were requested via `efetch` and all 41 were received in the XML batch (`missing_count: 0`, `reconciled: true`).
- **Record Types in Pilot XML**:
  - `PubmedArticle`: 39 standard journal articles.
  - `PubmedBookArticle`: 2 NCBI Bookshelf chapters (`PMID 28520369` and `PMID 28520347` from *Medical Genetics Summaries*).
- **Publication Dates**:
  - `Year_Month_Day`: 22
  - `Year_Month`: 10
  - `Year`: 5
  - `Year_Season`: 2
- **Current Blocker**: PubMed parser implementation is **BLOCKED** until full Phase 1 acquisition is approved, completed, and verified.

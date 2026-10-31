# Phase 2: Source Data Profile (Empirically Measured & Verified)

> **Status**: Fully updated following the acquisition and verification of the full PubMed corpus (3,096 PMIDs) and official ClinPGx/CPIC haplotype definition archives (`clinpgxHaplotypes.zip` and `cpic.alleles.json`).
> All metrics and counts were computed deterministically via in-memory streaming of raw immutable archives.
> Zero files were extracted or modified under `data/raw/`.

---

## 1. Executive Summary & Raw Catalog Inventory

All Phase 1 and Phase 1b raw archives and manifests are verified with 100% cryptographic SHA-256 match and 0 errors:

| Source Archive / Stream | Contained File | Format | Record Count | Encoding | Delimiter | Max Field Length (Characters) | Max Field Column |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `genes.zip` | `genes.tsv` | TSV | **25,041** | UTF-8 | Tab (`\t`) | 1,808 | `Cross-references` |
| `drugs.zip` | `drugs.tsv` | TSV | **3,770** | UTF-8 | Tab (`\t`) | **148,743** | `Brand Mixtures` |
| `chemicals.zip` | `chemicals.tsv` | TSV | **5,329** | UTF-8 | Tab (`\t`) | **148,743** | `Brand Mixtures` |
| `variants.zip` | `variants.tsv` | TSV | **7,692** | UTF-8 | Tab (`\t`) | 14,181 | `Synonyms` |
| `clinicalVariants.zip` | `clinicalVariants.tsv` | TSV | **5,192** | UTF-8 | Tab (`\t`) | 447 | `variant` |
| `drugLabels.zip` | `drugLabels.tsv` | TSV | **1,435** | UTF-8 | Tab (`\t`) | 1,118 | `Variants/Haplotypes` |
| `drugLabels.zip` | `drugLabels.byGene.tsv` | TSV | **239** | UTF-8 | Tab (`\t`) | 11,108 | `Label Names` |
| `summaryAnnotations.zip`| `summary_annotations.tsv` | TSV | **5,192** | UTF-8 | Tab (`\t`) | 447 | `Variant/Haplotypes` |
| `summaryAnnotations.zip`| `summary_ann_alleles.tsv` | TSV | **16,122** | UTF-8 | Tab (`\t`) | 1,364 | `Annotation Text` |
| `summaryAnnotations.zip`| `summary_ann_history.tsv` | TSV | **14,056** | UTF-8 | Tab (`\t`) | 436 | `Comment` |
| `summaryAnnotations.zip`| `summary_ann_evidence.tsv` | TSV | **15,542** | UTF-8 | Tab (`\t`) | 530 | `Score` |
| `variantAnnotations.zip`| `var_drug_ann.tsv` | TSV | **13,030** | UTF-8 | Tab (`\t`) | 2,402 | `Notes` |
| `variantAnnotations.zip`| `var_pheno_ann.tsv` | TSV | **14,560** | UTF-8 | Tab (`\t`) | 1,816 | `Notes` |
| `variantAnnotations.zip`| `var_fa_ann.tsv` | TSV | **2,189** | UTF-8 | Tab (`\t`) | 1,481 | `Notes` |
| `variantAnnotations.zip`| `study_parameters.tsv` | TSV | **36,083** | UTF-8 | Tab (`\t`) | 777 | `Characteristics` |
| `relationships.zip` | `relationships.tsv` | TSV | **246,714** | UTF-8 | Tab (`\t`) | 3,239 | `PMIDs` |
| `guidelineAnnotations.json.zip`| 219 JSON files | JSON | **219** | UTF-8 | JSON | N/A | N/A |
| `clinpgxHaplotypes.zip` | `clinpgxHaplotypes_star_alleles.tsv` | TSV | **485** | UTF-8 | Tab (`\t`) | 224 | `HGVS` |
| `clinpgxHaplotypes.zip` | `clinpgxHaplotypes_named_alleles.tsv`| TSV | **758** | UTF-8 | Tab (`\t`) | 158 | `HGVS` |
| `cpic.alleles.json` | JSON stream | JSON | **3,813** | UTF-8 | JSON | N/A | N/A |
| `pubmed (Full XML)` | 16 XML batch files | XML | **3,096** | UTF-8 | XML | N/A | N/A |

---

## 2. In-Depth Empirical Findings

### 2.1 Identity: `drugs.tsv` vs `chemicals.tsv` & Synonym Collisions
- **Accession Overlap**:
  - `drugs.tsv` accessions: **3,770**
  - `chemicals.tsv` accessions: **5,329**
  - Overlap: Exactly **3,770** accessions appear in both files (100.0% of drugs are in chemicals).
  - Only in `drugs.tsv`: **0**
  - Only in `chemicals.tsv`: **1,559** (metabolites, environmental compounds, chemical reagents).
- **Primary Name Uniqueness**: Zero primary name collisions under differing accession IDs.
- **Architectural Decision**: A PharmGKB accession (`PA...`) represents a single canonical compound/chemical entity (`pg:chem:<number>`). The drug designation is an attribute (`is_drug = True`), never a separate canonical entity or secondary ID.
- **Synonym-Level Collisions (Case-Folded)**:
  - When case-folding synonyms and trade names across all 5,329 chemical accessions, **76 distinct surface forms** map to more than one accession (69 from trade names, 7 from alternate names).
  - High-impact collision examples:
    - `"desoxyn"` maps to 3 accessions: `PA450403` (methamphetamine), `PA449269` (dextroamphetamine), `PA448408` (amphetamine).
    - `"vitaped"` maps to 3 accessions: `PA451892` (cyanocobalamin), `PA451652` (thiamine), `PA451897` (pyridoxine).
    - `"epzicom"` maps to 2 accessions: `PA450163` (lamivudine), `PA448004` (abacavir) [combination product].
    - `"darvocet"` maps to 2 accessions: `PA448015` (acetaminophen), `PA165290927` (acetaminophen / propoxyphene napsylate).
    - `"ceredase"` maps to 2 accessions: `PA164742934` (imiglucerase), `PA164748093` (alglucerase).
    - `"gestormone"` maps to 2 accessions: `PA164745307` (allylestrenol), `PA451123` (progesterone).
    - `"doxil"` maps to 2 accessions: `PA164750492` (almitrine), `PA449412` (doxorubicin).
  - **Resolution Policy**: Colliding surface forms are classified as ambiguous aliases. They are **never** auto-merged. They are cataloged in `data/review/ambiguous_synonyms.jsonl`.

### 2.2 Character Field Limits & Brand Mixtures Integrity
- **Python CSV Field Size Limit**: Python's `csv.field_size_limit()` operates in **characters**, not bytes. The default limit is 131,072 characters (128 KB).
- **Measured Maximum Field Length**: **148,743 characters** in column `Brand Mixtures` of `drugs.tsv` (row 3,425) and `chemicals.tsv` (row 4,908), both corresponding to PharmGKB ID `PA451652` (`thiamine`).
- **Integrity Proof of the 148,743-Character Row**:
  - Row parsed row count equals expected total: `drugs.tsv` = 3,770 rows; `chemicals.tsv` = 5,329 rows.
  - Column count for row 3,425 is exactly 26 columns, matching the header column count exactly (0 column mismatches).
  - Unbalanced quote count across all rows: 0.
  - Truncated content preview:
    - First 150 characters: `"50 Plus Multiple Vitamins & Minerals (Biotin + Calcium (Calcium Carbonate) + Chromium (Chromium Hvp Chelate) + Copper (Copper Hvp Chelate) + D-Pantot...`
    - Last 150 characters: `... + Vitamin B2 (Riboflavin) + Vitamin B6 (Pyridoxine Hydrochloride) + Vitamin C (Ascorbic Acid) + Vitamin D + Vitamin E (D-Alpha Tocopheryl Acetate))"`
  - Cause: Multi-vitamin/mineral dietary supplements where thiamine is co-formulated with dozens of ingredients across thousands of commercial trade preparations.
- **Inconsistency Resolution**:
  - *Initial Report Claim*: Stated that clinical annotation narrative text fields exceeded 128 KB.
  - *Correction & Explanation*: When the first profile was executed, `csv.reader` threw `_csv.Error: field larger than field limit (131072)`. It was mistakenly assumed that clinical annotations were the cause because annotations contain narrative interpretations. Subsequent exact measurement revealed that all annotation text fields are strictly $\le 2,402$ characters (`Notes` in `var_drug_ann.tsv`). The *sole* field exceeding 128 KB in the entire ClinPGx corpus is `Brand Mixtures`.
- **Field Limit Setting**: Set `csv.field_size_limit(250000)` (characters). This accommodates 148,743 characters with a ~68% safety margin (101,257 characters) while failing loudly on corrupt runaway tokens.

### 2.3 Star Alleles & Haplotype Definition Files Profile
- **`clinpgxHaplotypes.zip`**:
  - `clinpgxHaplotypes_star_alleles.tsv` (**485 rows**, 6 columns):
    - Columns: `Accession ID`, `Gene`, `Allele Name`, `HGVS`, `Structural Variation`, `AMP Level`
    - Null counts: `Accession ID` (0), `Gene` (0), `Allele Name` (0), `HGVS` (11, 2.27%), `Structural Variation` (474, 97.73%), `AMP Level` (428, 88.25%).
    - Sample: `{'Accession ID': 'PA165818750', 'Gene': 'CYP2B6', 'Allele Name': '*1', 'HGVS': 'NG_007929.1:g.='}`
  - `clinpgxHaplotypes_named_alleles.tsv` (**758 rows**, 6 columns):
    - Columns: `Accession ID`, `Gene`, `Allele Name`, `HGVS`, `Structural Variation`, `AMP Level`
    - Null counts: `Accession ID` (0), `Gene` (0), `Allele Name` (0), `HGVS` (257, 33.91%), `Structural Variation` (758, 100%), `AMP Level` (745, 98.28%).
    - Sample: `{'Accession ID': 'PA166287823', 'Gene': 'ABCG2', 'Allele Name': 'rs2231142 reference (G)', 'HGVS': 'NG_032067.2:g.105152C='}`
- **`cpic.alleles.json`** (**3,813 allele definitions** across 22 pharmacogenes):
  - Keys per item: `allele` (containing `accessionId`, `name`, and nested `gene` with `accessionId` and `symbol`), and `guidelines` (empty array `[]` for all 3,813 entries).
- **Explicit Relationships Finding**:
  - **Zero files define star-allele to rsID or variant-to-allele relationship tables.**
  - `HGVS` provides RefSeq genomic coordinates (e.g. `NG_007929.1:g.5071C>T`), not rsIDs.
  - In `clinpgxHaplotypes_named_alleles.tsv`, exactly 4 rows contain `rs` inside the free-text `Allele Name` string, but no structured rsID column exists.
  - **Rule**: Star alleles/haplotypes are modeled as distinct canonical entities (`pg:haplo:<number>`). No inferred links to rsIDs will be generated.

### 2.4 Multi-Value Field Parsing & Quote-Aware Comma Splitting
- Profiling of `Trade Names` in `drugs.tsv` and `chemicals.tsv` using Python's `csv.reader`:
  - `drugs.tsv`: 1,759 records with trade names, 36 with quotes, 1,210 with commas, 0 unbalanced quote errors, 18,491 total trade names extracted.
  - Exactly 4 trade names contain literal commas protected by double quotes:
    - `PA166305281` (3-hydroxy darifenacin): `'UK-148,993'` (compound code).
    - `PA449283` (diazepam): `', Freudal"'` (quoted artifact).
    - `PA10140` (miglustat): `'Miglustat, Hydrochloride'` (salt nomenclature).
    - `PA450635` (nitric oxide): `'Amidogen, oxo-'` (systematic CAS name).
  - Naive comma splitting on these records would corrupt compound codes and salt designations.
  - **Rule**: All delimited multi-value fields (`Trade Names`, `Alternate Names`) must be parsed via `csv.reader` on the string to preserve quoted commas.

### 2.5 `relationships.tsv` Complete Endpoint Matrix & Dangling Analysis
- Total relationship rows: **246,714**.
- Endpoint occurrences by type across `Entity1` and `Entity2`:
  - `Chemical`: 127,660 (100% resolved against `chemicals.tsv`/`drugs.tsv`)
  - `SNV`: 122,122 (100% unmodeled in `variants.tsv` — genomic HGVS coordinates, e.g. `NC_000009.12:g.104941653G=`)
  - `Phenotype`: 118,704 (100% unmodeled — no phenotype archive selected in Phase 1)
  - `Variant`: 66,242 (66,086 resolved by `variants.tsv`; 156 dangling)
  - `Gene`: 40,662 (100% resolved against `genes.tsv`)
  - `StarAllele`: 13,052 (10,610 resolved by `clinpgxHaplotypes_star_alleles.tsv`; 12,478 resolved by `cpic.alleles.json`; 574 dangling)
  - `HlaAllele`: 3,580 (1,890 resolved by `cpic.alleles.json`; 1,690 dangling)
  - `Haplotype`: 1,014 (400 resolved by `clinpgxHaplotypes_named_alleles.tsv`; 694 resolved by `cpic.alleles.json`; 286 dangling)
  - `GeneCopyNumberVariation`: 392 (100% unmodeled)
- **Top Endpoint Pair Combinations**:
  1. `SNV -- Chemical` / `Chemical -- SNV`: 62,770 rows
  2. `SNV -- Phenotype` / `Phenotype -- SNV`: 59,340 rows
  3. `Variant -- Chemical` / `Chemical -- Variant`: 34,092 rows
  4. `Variant -- Phenotype` / `Phenotype -- Variant`: 31,868 rows
  5. `Gene -- Chemical` / `Chemical -- Gene`: 20,850 rows
  6. `StarAllele -- Chemical` / `Chemical -- StarAllele`: 13,052 rows
- **Dangling Row Count**: **191,466 rows** (77.61% of all relationship rows).
- **Modeling Policy**: In Phase 2, `relationships.tsv` will be parsed and typed in full. Edges whose endpoints do not exist in the primary entity registry are marked with `is_dangling = True` and preserved with verbatim source endpoint metadata. Zero rows are silently dropped.

---

## 3. PubMed Corpus Profile (Full Run)

### 3.1 Status & Reconciliation
- **Dated Directories under `data/raw/pubmed/`**:
  - `20261030_9a48695d` (`is_pilot = true`, 41 PMIDs, archived pilot baseline).
  - `20261031_7d1398e0` (`is_pilot = false`, **3,096 PMIDs**, full production run).
- **Pair Breakdown & Esearch Totals (Retrieved 2026-10-31)**:
  - `CYP2C19_clopidogrel`: 1,432 PMIDs requested, 1,432 retrieved.
  - `CYP2C9_warfarin`: 1,409 PMIDs requested, 1,409 retrieved.
  - `VKORC1_warfarin`: 978 PMIDs requested, 978 retrieved.
  - `SLCO1B1_simvastatin`: 141 PMIDs requested, 141 retrieved.
  - Sum of pair candidate slots: 3,960.
  - Unique deduplicated PMIDs: **3,096**.
  - Total requested: 3,096; total received: 3,096; missing: 0 (`reconciled: true`).
  - Subset Check: All 41 pilot PMIDs are strictly contained within the 3,096 full corpus PMIDs.

### 3.2 Content & Structure Breakdown
- **Record Types**:
  - `<PubmedArticle>`: **3,085** journal articles.
  - `<PubmedBookArticle>`: **11** NCBI Bookshelf chapters from *Medical Genetics Summaries*.
- **Abstract Availability**:
  - 100.0% (**3,096 of 3,096**) contain abstracts.
- **Top Abstract Section Labels / NlmCategories**:
  1. `UNLABELED` (standard single-paragraph abstracts): 1,591
  2. `RESULTS`: 1,213
  3. `METHODS`: 959
  4. `CONCLUSIONS`: 666
  5. `CONCLUSION`: 654
  6. `BACKGROUND`: 545
  7. `OBJECTIVE`: 178
- **MeSH Headings**:
  - Articles with MeSH terms: **2,678** (86.5%).
  - Articles without MeSH terms: **418** (recent 2024-2026 pre-indexing articles and all 11 Book Articles).
  - Top MeSH Descriptors:
    1. Humans: 2,607
    2. Male: 1,509
    3. Female: 1,413
    4. Middle Aged: 1,229
    5. Genotype: 1,133
    6. Aged: 1,061
    7. Warfarin: 864
    8. Clopidogrel: 785
    9. Treatment Outcome: 760
- **Publication Year Distribution**:
  - Range: **1993 to 2026**.
  - Top Years: 2013 (206), 2012 (198), 2015 (182), 2014 (175), 2016 (168), 2021 (164).

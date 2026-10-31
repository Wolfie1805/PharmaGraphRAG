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
    - **Free Text Rule**: Named alleles such as `"rs2231142 reference (G)"` contain rsID strings embedded in free-text names. In accordance with project rules, **zero rsIDs will be extracted or parsed from allele names or free text**. The name is preserved exactly as given.
- **`cpic.alleles.json`** (**3,813 allele definitions** across exactly **22 pharmacogenes**):
  - Genes in file: `CACNA1S`, `CFTR`, `CYP2B6`, `CYP2C19`, `CYP2C8`, `CYP2C9`, `CYP2D6`, `CYP3A4`, `CYP3A5`, `CYP4F2`, `DPYD`, `G6PD`, `HLA-A`, `HLA-B`, `MT-RNR1`, `NAT2`, `NUDT15`, `RYR1`, `SLC6A4`, `SLCO1B1`, `TPMT`, `UGT1A1`.
  - Keys per item: `allele` (containing `accessionId`, `name`, and nested `gene` with `accessionId` and `symbol`), and `guidelines` (empty array `[]` for all 3,813 entries).
- **Explicit Relationships Finding**:
  - **Zero files define star-allele to rsID or variant-to-allele relationship tables.**
  - `HGVS` provides RefSeq genomic coordinates (e.g. `NG_007929.1:g.5071C>T`), not rsIDs.
  - **Rule**: Star alleles/haplotypes are modeled as distinct canonical entities (`pg:haplo:<number>`). No inferred links to rsIDs will be generated.

### 2.4 Multi-Value Field Parsing, Quote-Aware Splitting & Source Artifacts
- **Delimited Multi-Value Columns**: `Trade Names` and `Alternate Names` in `drugs.tsv` and `chemicals.tsv`.
- **Chemicals vs Drugs Profile Comparison**:
  - `drugs.tsv`: 1,759 records with trade names, 36 with quotes, 14 with parentheses, 1,210 with commas. Total 18,433 trade names extracted using `skipinitialspace=True`.
  - `chemicals.tsv`: 1,812 records with trade names, 36 with quotes, 14 with parentheses, 1,219 with commas. Total 18,500 trade names extracted using `skipinitialspace=True`.
- **Reconciliation of the 48 Rows with Commas and Quotes/Parens**:
  - In `drugs.tsv` and `chemicals.tsv`, exactly **48 rows** contain commas together with either quotes or parentheses:
    - **34 rows** contain quotes and commas.
    - **14 rows** contain parentheses and commas.
    - Zero rows contain both quotes and parentheses. ($34 + 14 = 48$).
- **Handling of Quoted Items & `skipinitialspace=True`**:
  - Standard `csv.reader(io.StringIO(raw))` without `skipinitialspace=True` treats leading whitespace after commas as token content, which causes quotes preceded by spaces (e.g., `, "Faustan,"`) to be treated as literals rather than delimiter quotes.
  - Using `csv.reader(io.StringIO(raw), skipinitialspace=True)` strictly preserves all quoted compound codes and inverted names (e.g. `"UK-148,993"`, `"Miglustat, Hydrochloride"`, `"Amidogen, oxo-"`, `"Benzoic acid, benzyl ester"`).
- **Parenthetical Commas & Handling**:
  - Quote-aware parsing does NOT protect commas inside parentheses, because parentheses are not standard CSV quoting delimiters.
  - Across all 14 rows containing parentheses and commas, in 13 rows the parentheses are standard single-item qualifiers (e.g., `'Zovirax Injection (Zovirax sodium)'`, `'DMCT (antibiotic)'`, `'Depocyt (liposomal)'`, `'Winstrol Depot (intramuscular injection)'`, `'K 12 (surfactant)'`).
  - Exactly **1 row** (`PA164743704`, antithymocyte globulin) contains an unbalanced parenthetical comma error in the source data:
    `Raw: ATG-Fresenius, ATG-Fresenius S, Genzyme, Genzyme), Thymoglobulin (SangStat Medical, Thymoglobulin SangStat Medical`
    Here `Genzyme)` has an un-matched closing parenthesis, and `Thymoglobulin (SangStat Medical, ...` has an un-matched opening parenthesis split across a comma.
- **Malformed Source Artifacts Flagged**:
  - Across all 18,433/18,500 trade names, exactly **3 items** represent malformed source artifacts:
    1. `PA449283` (diazepam): `'Faustan,'` (dangling trailing comma embedded in source string `"Faustan,"`).
    2. `PA164743704` (antithymocyte globulin): `'Genzyme)'` (unbalanced closing parenthesis).
    3. `PA164743704` (antithymocyte globulin): `'Thymoglobulin (SangStat Medical'` (unbalanced opening parenthesis).
  - **Policy**: These items are preserved verbatim in the raw data, flagged with `is_artifact = True`, and are **excluded from being loaded as resolver synonyms**.

### 2.5 `relationships.tsv` Complete Endpoint Matrix, Join Keys & SNV Findings
- Total relationship rows: **246,714**.
- All endpoint resolution joins are performed using **exact accession / ID joins only** (zero name joins):

| Endpoint Type | Total Endpoints | Join Key | Target File | Resolved (ID Join) | Dangling (ID Join) | Dangling % |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Chemical** | 127,660 | `PharmGKB Accession Id` (`PA...`) | `chemicals.tsv` / `drugs.tsv` | **127,660** | **0** | 0.0% |
| **SNV** | 122,122 | None (No dedicated file) | N/A | **0** | **122,122** | 100.0% |
| **Phenotype** | 118,704 | None (No dedicated file) | N/A | **0** | **118,704** | 100.0% |
| **Variant** | 66,242 | `Variant ID` (`PA...`) | `variants.tsv` | **66,086** | **156** | 0.24% |
| **Gene** | 40,662 | `PharmGKB Accession Id` (`PA...`) | `genes.tsv` | **40,662** | **0** | 0.0% |
| **StarAllele** | 13,052 | `PharmGKB Accession Id` (`PA...`) | `clinpgxHaplotypes` / `cpic.alleles.json` | **12,478** | **574** | 4.40% |
| **HlaAllele** | 3,580 | `PharmGKB Accession Id` (`PA...`) | `cpic.alleles.json` | **1,890** | **1,690** | 47.21% |
| **Haplotype** | 1,014 | `PharmGKB Accession Id` (`PA...`) | `clinpgxHaplotypes` / `cpic.alleles.json` | **694** | **320** | 31.56% |
| **GeneCopyNumberVariation** | 392 | None (No dedicated file) | N/A | **0** | **392** | 100.0% |

- **Total Dangling Relationship Rows**: **191,466 rows (77.61%)** involve at least one endpoint lacking a dedicated entity definition file.
- **Section B.2 Investigation: SNV Endpoints vs `variants.tsv`**:
  - SNV endpoint IDs in `relationships.tsv` (13,358 unique IDs) are `PA1663...` accessions, which have **0 matches** in `variants.tsv` `Variant ID` (which uses `PA1661...`).
  - SNV endpoint Names in `relationships.tsv` are genomic HGVS coordinates (e.g. `NC_000009.12:g.104941653G=`, `NC_000017.11:g.47731941T>C`).
  - Testing an exact string join against individual tokens in `variants.tsv`'s `Synonyms` column:
    - **1,694 SNV Names** match an exact synonym token in `variants.tsv` (e.g., `'NC_000017.11:g.47731941T>C'` matches rsID `rs2229774`).
    - **11,664 SNV Names** (87.3%) do NOT match any token in `variants.tsv` `Synonyms`, because they use reference allele '=' notation (e.g. `g.104941653G=`) or legacy gene-centric coordinates (`MED4 125+938C=`).
  - Zero SNV names match HGVS strings in `clinpgxHaplotypes_star_alleles.tsv` or `clinpgxHaplotypes_named_alleles.tsv`.
- **Dangling Endpoints Architecture Decision (Section B.1 & B.2 Proposal)**:
  - For endpoint types not defined by any dedicated file (`Phenotype`, `SNV`, `GeneCopyNumberVariation`, and unlisted `StarAllele`, `HlaAllele`, `Haplotype`, `Variant`), create entities directly from `relationships.tsv` using the `id`, `name`, and `type` the file itself provides, with `defined_by = "relationships_only"` and full provenance.
  - The type label is kept exactly as the source states, with zero subclassification.
  - All edges connecting `relationships_only` endpoints have `is_dangling = True`.
  - For the 1,694 SNVs that match an exact `variants.tsv` synonym, we propose logging them to `data/review/snv_variant_exact_matches.jsonl` while keeping the SNV entity distinct from the `pg:var:` rsID variant entity until human approval.

### 2.6 Cross-Entity Surface Form Collisions & Source Quirks
- **Cross-Entity Collisions (Gene vs Chemical)**:
  - Checking case-folded gene symbols and names against chemical names and synonyms identified exactly **26 cross-entity collisions**:
    - `adm` $\rightarrow$ Gene `PA24580` (`ADM`) vs Chemical `PA449412` (`ADM` [doxorubicin synonym]).
    - `apc` $\rightarrow$ Gene `PA24875` (`APC`) vs Chemical `PA166131559` (`APC` [aspirin/paracetamol/caffeine]).
    - `asparaginase` $\rightarrow$ Gene `PA166180563` (`asparaginase`) vs Chemical `PA448492` (`asparaginase`).
    - `avil` $\rightarrow$ Gene `PA38380` (`AVIL`) vs Chemical `PA164744506` (`AVIL` [pheniramine]).
    - `coagulation factor ix` $\rightarrow$ Gene `PA27954` (`coagulation factor IX`) vs Chemical `PA164744952` (`coagulation factor ix`).
    - `cp` $\rightarrow$ Gene `PA26815` (`CP`) vs Chemical `PA449165` (`CP` [cyclophosphamide]).
    - `cyren` $\rightarrow$ Gene `PA162380533` (`CYREN`) vs Chemical `PA449307` (`Cyren` [diethylstilbestrol]).
    - `dbh` $\rightarrow$ Gene `PA136` (`DBH`) vs Chemical `PA164754914` (`DBH`).
    - `dbi` $\rightarrow$ Gene `PA27158` (`DBI`) vs Chemical `PA1000` (`DBI` [phenformin]).
    - `erythropoietin` $\rightarrow$ Gene `PA27833` (`erythropoietin`) vs Chemical `PA10072` (`erythropoietin`).
  - **Handling**: The entity resolver remains strictly type-aware. All 26 cross-entity collisions are cataloged in `data/review/cross_entity_collisions.jsonl`.
- **Source Quirks Recorded as Facts**:
  - Source facts such as `"doxil"` mapping to both `PA164750492` (almitrine) and `PA449412` (doxorubicin) are recorded verbatim as asserted in ClinPGx. They are flagged with `is_ambiguous = True` without artificial correction.

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

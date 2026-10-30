# ClinPGx / PharmGKB File Selection & Catalog

**Date Checked:** 2026-10-30  
**Official Downloads Page:** https://www.clinpgx.org/downloads  
**Official API Catalog Endpoint:** https://api.clinpgx.org/v1/data/file/data/?view=min  
**Download Endpoint Pattern:** `https://api.clinpgx.org/v1/download/file/data/<fileName>`  
**Release Date / Cadence Documentation:**
- UI Notice on Downloads Page: *"These files are generated on the 6th of every month."*
- API Metadata on Downloadable Archives: `lastModified` timestamp on current active files is `2026-10-05T00:42:40-07:00` (October 5, 2026).
- *Discrepancy Note:* The server cron generates files on the night between the 5th and 6th (UTC vs Pacific Time / US PDT), resulting in an effective `2026-10-05` file timestamp for the October 2026 monthly release.
**License:** Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)  
**Terms of Use:** Research purposes only; commercial resale prohibited under ClinPGx Terms and Conditions of Use.

---

## 1. Complete Official Catalog of Available Downloads

Verbatim descriptions copied directly from the official ClinPGx downloads page UI:

| File Name | Section / Category | Description (Verbatim from Official Page) | Format | Size (approx) |
|---|---|---|---|---|
| `summaryAnnotations.zip` | Annotations Data | Summary annotations. | TSV | 1,236,737 bytes (~1.24 MB) |
| `variantAnnotations.zip` | Annotations Data | Variant annotations. | TSV | 4,296,635 bytes (~4.30 MB) |
| `relationships.zip` | Variant, Gene and Drug Relationship Data | Relationships summarized from ClinPGx annotations. | TSV | 4,300,897 bytes (~4.30 MB) |
| `guidelineAnnotations.json.zip` | Clinical Guideline Annotations | Detailed clinical guideline annotations in JSON format | JSON | 854,307 bytes (~854 KB) |
| `drugLabels.zip` | Drug Label Annotations | Drug label annotations in TSV format | TSV | 60,036 bytes (~60 KB) |
| `pathways-biopax.zip` | Pathways | Pathways data in BioPAX XML format | BioPAX XML | 634,058 bytes (~634 KB) |
| `pathways-tsv.zip` | Pathways | Pathways data in TSV format | TSV | 205,671 bytes (~206 KB) |
| `pathways.json.zip` | Pathways | Pathways data in JSON format | JSON | 2,041,049 bytes (~2.04 MB) |
| `clinicalVariants.zip` | Clinical Variant Data | This file contains a list of variant-drug pairs and level of evidence for all clinical annotations in TSV format | TSV | 224,294 bytes (~224 KB) |
| `occurrences.zip` | Literature Occurrence | A list of objects that occur in ClinPGx literature and pathways. | TSV | 3,444,832 bytes (~3.44 MB) |
| `genes.zip` | Primary Data | A summary of the gene information used by ClinPGx and how it has been annotated. | TSV | 2,905,579 bytes (~2.91 MB) |
| `variants.zip` | Primary Data | A summary of variants annotated by ClinPGx that have also been tracked in dbSNP. | TSV | 908,661 bytes (~909 KB) |
| `drugs.zip` | Primary Data | Summaries of chemical information annotated by ClinPGx. The list of drugs is a subset of the list of all chemicals annotated by ClinPGx. | TSV | 679,044 bytes (~679 KB) |
| `chemicals.zip` | Primary Data | Summaries of chemical information annotated by ClinPGx. All chemicals annotated by ClinPGx. | TSV | 1,500,000 bytes (~1.50 MB) |
| `phenotypes.zip` | Primary Data | A summary of disease and other phenotypes that have been annotated by ClinPGx. | TSV | 187,493 bytes (~187 KB) |
| `automated_annotations.zip` | Automated Annotations | This file contains possible relationship between a variant and a drug in a sentence from an abstract in PubMed or an article in PubMed Central. Sentences are identified automatically by a text mining algorithm. Compiled October 2020 | TSV | ~16 MB |
| `pharmgkb_haplotype_frequencies_AllOfUs.zip` | Other Datasets | Haplotype, phenotype, and activity score frequencies from an analysis of the AllOfUs dataset using PharmCAT. | TSV | 58,421 bytes (~58 KB) |
| `pharmgkb_haplotype_frequencies_UKBB.zip` | Other Datasets | Haplotype frequencies from an analysis of the UK Biobank dataset using PharmCAT. Data from Frequencies of pharmacogenomic alleles across biogeographic groups in a large-scale biobank (PMID: 37757824) | TSV | 29,673 bytes (~30 KB) |
| `ClinPGx_Training_Exercises.zip` | Other Datasets | These exercises are intended to help new users familiarize themselves with the ClinPGx website. | ZIP | Attachment |

---

## 2. Confirmed 10-Archive Acquisition Selection for Phase 1

The verified selection contains exactly **10 archives** covering all required entities and relationships:

| # | File Name | Domain Coverage | Reason for Inclusion |
|---|---|---|---|
| 1 | `genes.zip` | Genes | Master gene entities, cross-references, and symbols. |
| 2 | `drugs.zip` | Drugs | Curated drug entities and indications. |
| 3 | `chemicals.zip` | Chemicals | All chemical entities including active metabolites and prodrugs. |
| 4 | `variants.zip` | Variants | dbSNP-tracked variants and RSIDs. |
| 5 | `clinicalVariants.zip` | Variants & Evidence | Variant-drug pairs and evidence levels. |
| 6 | `summaryAnnotations.zip` | Clinical Annotations | Curated summary annotations for variant-drug combinations. |
| 7 | `variantAnnotations.zip` | Clinical Annotations | Granular literature-level variant annotations. |
| 8 | `drugLabels.zip` | Drug Label Annotations | FDA and international PGx drug label annotations. |
| 9 | `guidelineAnnotations.json.zip` | Guideline Annotations | CPIC and international PGx clinical guideline recommendations. |
| 10 | `relationships.zip` | Relationships | Curated relationships connecting variants, genes, and drugs. |

**Total Confirmed Archives:** Exactly 10 archives.  
**Catalog API Snapshot:** In addition to these 10 archives, the live API response (`api.clinpgx.org/v1/data/file/data/?view=min`) will be saved as an immutable raw artifact (`clinpgx_file_catalog.json`) in its own dated run directory.

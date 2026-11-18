# Data Licenses & Usage Policies

| Source Archive / Stream | License | License URL | Attribution Text | Date Checked | Redistribution Notes | Open Questions |
|---|---|---|---|---|---|---|
| **ClinPGx Core TSVs** (`genes.zip`, `drugs.zip`, `chemicals.zip`, `variants.zip`, `clinicalVariants.zip`, `drugLabels.zip`, `relationships.zip`, `summaryAnnotations.zip`, `variantAnnotations.zip`) | Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0) | https://creativecommons.org/licenses/by-sa/4.0/ | "Clinical annotations were obtained from ClinPGx (www.clinpgx.org) [accessed 2026-10-30]. Citation: M. Whirl-Carrillo, et al. 'An evidence-based framework for evaluating pharmacogenomics knowledge for personalized medicine' Clin Pharmacol Ther (2021) 110(3):563-572. PMID: 34216021." | 2026-10-30 | Permitted for research purposes. Under ClinPGx Terms and Conditions of Use: "to use the data for research purposes and not with any intent to offer all or any part of the data for sale as a commercial item". All raw and derived ClinPGx data stays private and local. Do not push to public repositories or public DVC remotes. Preserve attribution wherever data is used. | None. Research use confirmed. |
| **ClinPGx Haplotypes** (`clinpgxHaplotypes.zip`) | Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0) | http://creativecommons.org/licenses/by-nc-sa/4.0/ | "Haplotype definitions were obtained from ClinPGx (https://www.clinpgx.org/page/citingClinpgx) [accessed 2026-10-31]." | 2026-10-31 | Explicit LICENSE.txt packaged inside archive: "This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International license... 1. Attribution: You must give appropriate credit to ClinPGx... 2. NonCommercial: You may not use the material for commercial purposes... 3. ShareAlike: If you alter, amend, reuse or otherwise change ClinPGx data you agree that if you distribute such product, all recipients shall first agree to be subject to this license. Under no circumstances can ClinPGx data be sold for other's private or commercial use." | All derivative outputs remain internal/private. |
| **CPIC Alleles** (`cpic.alleles.json`) | Creative Commons Zero 1.0 Universal (CC0 1.0) Public Domain Dedication | https://creativecommons.org/publicdomain/zero/1.0/ | "CPIC allele definitions and guideline status were obtained from the Clinical Pharmacogenetics Implementation Consortium (CPIC) (https://cpicpgx.org) [accessed 2026-10-31]." | 2026-10-31 | Public domain dedication: "To the extent possible under law, CPIC has waived all copyright and related or neighboring rights to CPIC guidelines and associated data tables." Free of copyright restrictions. Attribution requested by project. | None. |
| **PubMed / NLM (NCBI E-utilities)** | U.S. Government Public Domain (metadata/citations); individual third-party copyright on abstracts & full text | https://www.ncbi.nlm.nih.gov/About/disclaimer.html | "Data sourced from the National Library of Medicine (NLM) / National Center for Biotechnology Information (NCBI) via E-utilities. NLM does not endorse or recommend this or any other application." | 2026-10-30 | NLM-generated bibliographic records are public domain in the US. However, abstracts may be copyrighted by journal publishers/authors. Redistribution of bulk abstracts commercially or publicly requires caution; fair-use and publisher rights apply. Full-text must never be fetched or redistributed. | None. Research scope limited to metadata and abstracts. |
| **NRCeS Common Drug Codes for India (Flat Files Package)** (`CommonDrugCodesForIndia_FlatFilePackage.zip`) | Creative Commons Attribution 4.0 International (CC BY 4.0) + SNOMED CT Affiliate License clauses (India territorial restriction; third-party brand/trade name copyrights) | https://creativecommons.org/licenses/by/4.0/ | "Common Drug Codes for India (Flat Files Package) produced by National Resource Centre for EHR Standards (NRCeS) at Centre for Development of Advanced Computing (C-DAC), Pune [checked 2026-11-18]." | 2026-11-18 | Keep NRCeS-derived data private and local for now. Redistributable/derivatives permitted within India under SNOMED CT Affiliate License clauses; brand/trade names remain copyright of their respective owners. Do not push raw or NRCeS-derived data to public repositories or public DVC remotes. | Commercial use or public release of NRCeS-derived data requires review. |

---

## Detailed Terms & Policies Summary

### 1. ClinPGx / PharmGKB Terms of Use & Data Usage Policy
- **Governing Body:** NIH-sponsored research project (U24HG010615) hosted at Stanford University.
- **Licenses:**
  - Core files: CC BY-SA 4.0.
  - Haplotype archive (`clinpgxHaplotypes.zip`): CC BY-NC-SA 4.0 (explicit `LICENSE.txt`).
- **Exact Policy Quotes (from `https://www.clinpgx.org/page/dataUsagePolicy` and `clinpgxHaplotypes.zip#LICENSE.txt`):**
  - **Attribution Requirement:** *"You must give appropriate credit to PharmGKB, provide a link to this license, and indicate if changes were made. You may do so in any reasonable manner, but not in any way that suggests PharmGKB endorses you or approves of your use."*
  - **NonCommercial Requirement (`clinpgxHaplotypes.zip`):** *"You may not use the material for commercial purposes... Under no circumstances can ClinPGx data be sold for other's private or commercial use."*
  - **Share-Alike Requirement:** *"If you alter, amend, reuse or otherwise change ClinPGx/PharmGKB data, you must distribute your contributions using this license as well. You may not apply legal terms or technological measures that legally restrict others from doing anything this license permits."*
  - **Terms and Conditions of Use (Commercial Restriction Source):**
    > *"By accessing the data on the website, you are agreeing to the following:*
    > *1. to collect statistics about your general use of the website through third-party analytics services (e.g. Google Analytics),*
    > *2. to use the data for research purposes and not with any intent to offer all or any part of the data for sale as a commercial item, and*
    > *3. acknowledge that the accuracy of the data in this knowledge base cannot be guaranteed and must be considered when using this data."*
  - **Warranty Disclaimer:** *"This data is provided 'as is', 'where is' and without any express or implied warranties... In no event shall Stanford University, nor its agents, employers or representatives be liable for any direct, indirect, incidental, special, exemplary, or consequential damages..."*

### 2. CPIC (Clinical Pharmacogenetics Implementation Consortium) Data Policy
- **License:** CC0 1.0 Universal (Public Domain).
- **Exact Terms Quote:** *"Creative Commons CC0 1.0 Universal (CC0 1.0) Public Domain Dedication. To the extent possible under law, the Clinical Pharmacogenetics Implementation Consortium (CPIC) has waived all copyright and related or neighboring rights to CPIC guidelines and associated data tables."*

### 3. PubMed / NLM / NCBI Data Usage & E-utilities Policy
- **Base URL:** Programmatic requests must target `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`.
- **Rate Limits:** 
  - Standard (no API key): strictly $\le 3$ requests/second. Default configured: 2 req/s.
  - With NCBI API key: up to 10 requests/second. Default configured: 8 req/s.
- **Mandatory Parameters:** Every request must include `tool=<client_name>` and `email=<contact_email>`.
- **Copyright Boundaries:**
  - NLM does not claim copyright on PubMed bibliographic records; individual journal publishers and authors typically hold copyright on abstracts.
  - Scope is strictly limited to metadata and abstracts for research grounding. Full text is never fetched.
  - PubMed abstract excerpts are shown only as short quoted excerpts with source IDs; abstract copyright and NLM terms are "unverified" until I review them.

---

## 4. Privacy & Answer Mode Architecture
- Default answer mode runs locally with no external service; no ClinPGx-derived text is sent anywhere unless the optional local model mode is used, which also stays on this machine.

---

## 5. Frontend Self-Hosted Typography Licenses
- **Sora (`@fontsource/sora` pinned to v5.3.0):**
  - **License:** SIL Open Font License, Version 1.1 (OFL-1.1).
  - **Copyright:** Copyright 2019 The Sora Project Authors (https://github.com/huertatipografica/sora).
  - **Redistribution:** Self-hosted package bundled locally with zero external network calls. Subsets restricted to Latin.
- **Inter (`@fontsource/inter` pinned to v5.3.0):**
  - **License:** SIL Open Font License, Version 1.1 (OFL-1.1).
  - **Copyright:** Copyright (c) 2016-2020 The Inter Project Authors (https://github.com/rsms/inter).
  - **Redistribution:** Self-hosted package bundled locally with zero external network calls. Subsets restricted to Latin.
- **JetBrains Mono (`@fontsource/jetbrains-mono` pinned to v5.3.0):**
  - **License:** SIL Open Font License, Version 1.1 (OFL-1.1).
  - **Copyright:** Copyright 2020 The JetBrains Mono Project Authors (https://github.com/JetBrains/JetBrainsMono).
  - **Redistribution:** Self-hosted package bundled locally with zero external network calls. Subsets restricted to Latin.

---

## 6. Backend Runtime Dependency Licenses
- **DuckDB (`duckdb==2.0.0`, pinned in `requirements-lock.txt`):**
  - **Package Metadata Classifier:** `License :: OSI Approved :: MIT License` (read from installed `duckdb==2.0.0` metadata on 2026-11-18).
  - **Verbatim License Text** (from `.venv/Lib/site-packages/duckdb-2.0.0.dist-info/licenses/LICENSE`):
    > Copyright 2018-2026 Stichting DuckDB Foundation
    >
    > Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
    >
    > The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
    >
    > THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
  - **Note on Submodule:** The installed wheel also includes an unused experimental module (`duckdb/experimental/spark/LICENSE`, Apache License Version 2.0). PharmaGraph uses only core in-memory DuckDB (`duckdb.connect(":memory:")`).

---

## 7. NRCeS Common Drug Codes for India (Flat Files Package)
- **Date Checked:** `2026-11-18`
- **Source Page:** `https://www.nrces.in/services/national-releases` (downloaded manually by user; copied write-once to `data/raw/nrces/20261118_2cab0068/CommonDrugCodesForIndia_FlatFilePackage.zip`, SHA-256 `aebd30ac95d73accf573c86fd4dae1dc90eff03ae0fbcd312bc761011e88270a`).
- **Required CC BY 4.0 Attribution Text:**
  > Common Drug Codes for India, National Resource Centre for EHR Standards (NRCeS), C-DAC, CC BY 4.0, https://www.nrces.in/services/national-releases; changes: parsed into tables
- **Storage Policy:** NRCeS-derived data stays private and local.
- **Open Items:**
  1. Commercial use or public release of NRCeS-derived data requires review.
  2. SNOMED CT Affiliate License paragraph: *"The Flat Files Package contain some SNOMED CT codes (identifiers) and Terms from its International Release. The usage of SNOMED CT International Release content is governed by relevant clauses of SNOMED CT Affiliate License extended to the user of this package."*
  3. "Within India" redistribution and derivative wording: *"The Licensee can redistribute this package within India. The Licensee can create derivatives or implementation-related products and services using this package within India."*
  4. NRCeS-derived data stays private and local.
- **Verbatim `CommonDrugCodesForIndia_FlatFilePackage/License.txt`** (read directly in memory from the archive on `2026-11-18`):
  > Copyright (c) 2019, Centre for Development of Advanced Computing (C-DAC), Pune
  > All rights reserved.
  >
  > The Common Drug Codes for India (Flat Files Package) is produced by National Resource Centre for EHR Standards (NRCeS) at Centre for Development of Advanced Computing (C-DAC), Pune under the terms of the Creative Commons Attribution 4.0 International Public License, https://creativecommons.org/licenses/by/4.0/
  >
  > Additional information about this license for use of Common Drug Codes for India (Flat Files Package):
  >
  > The Common Drug Codes for India (Flat Files Package) is a managed list of Common Drug Codes for India covering a list of unique identifiers and terms. The Flat Files Package contain some SNOMED CT codes (identifiers) and Terms from its International Release. The usage of SNOMED CT International Release content is governed by relevant clauses of SNOMED CT Affiliate License extended to the user of this package.
  >
  > SNOMED CT® was originally created by the College of American Pathologists.  "SNOMED" and "SNOMED CT" are registered trademarks of International Health Terminology Standards Development Organisation, trading as SNOMED International.
  >
  > The Licensee can redistribute this package within India. The Licensee can create derivatives or implementation-related products and services using this package within India.
  >
  > The Brand names and any trade names are copyright of their respective owners.
  >
  > C-DAC does not warrant the accuracy, completeness, or adequacy of content. The content provided is intended but not promised or guaranteed to be current, complete and up-to-date.


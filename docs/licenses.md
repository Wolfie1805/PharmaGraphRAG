# Data Licenses & Usage Policies

| Source Archive / Stream | License | License URL | Attribution Text | Date Checked | Redistribution Notes | Open Questions |
|---|---|---|---|---|---|---|
| **ClinPGx Core TSVs** (`genes.zip`, `drugs.zip`, `chemicals.zip`, `variants.zip`, `clinicalVariants.zip`, `drugLabels.zip`, `relationships.zip`, `summaryAnnotations.zip`, `variantAnnotations.zip`) | Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0) | https://creativecommons.org/licenses/by-sa/4.0/ | "Clinical annotations were obtained from ClinPGx (www.clinpgx.org) [accessed 2026-10-30]. Citation: M. Whirl-Carrillo, et al. 'An evidence-based framework for evaluating pharmacogenomics knowledge for personalized medicine' Clin Pharmacol Ther (2021) 110(3):563-572. PMID: 34216021." | 2026-10-30 | Permitted for research purposes. Under ClinPGx Terms and Conditions of Use: "to use the data for research purposes and not with any intent to offer all or any part of the data for sale as a commercial item". All raw and derived ClinPGx data stays private and local. Do not push to public repositories or public DVC remotes. Preserve attribution wherever data is used. | None. Research use confirmed. |
| **ClinPGx Haplotypes** (`clinpgxHaplotypes.zip`) | Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0) | http://creativecommons.org/licenses/by-nc-sa/4.0/ | "Haplotype definitions were obtained from ClinPGx (https://www.clinpgx.org/page/citingClinpgx) [accessed 2026-10-31]." | 2026-10-31 | Explicit LICENSE.txt packaged inside archive: "This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International license... 1. Attribution: You must give appropriate credit to ClinPGx... 2. NonCommercial: You may not use the material for commercial purposes... 3. ShareAlike: If you alter, amend, reuse or otherwise change ClinPGx data you agree that if you distribute such product, all recipients shall first agree to be subject to this license. Under no circumstances can ClinPGx data be sold for other's private or commercial use." | All derivative outputs remain internal/private. |
| **CPIC Alleles** (`cpic.alleles.json`) | Creative Commons Zero 1.0 Universal (CC0 1.0) Public Domain Dedication | https://creativecommons.org/publicdomain/zero/1.0/ | "CPIC allele definitions and guideline status were obtained from the Clinical Pharmacogenetics Implementation Consortium (CPIC) (https://cpicpgx.org) [accessed 2026-10-31]." | 2026-10-31 | Public domain dedication: "To the extent possible under law, CPIC has waived all copyright and related or neighboring rights to CPIC guidelines and associated data tables." Free of copyright restrictions. Attribution requested by project. | None. |
| **PubMed / NLM (NCBI E-utilities)** | U.S. Government Public Domain (metadata/citations); individual third-party copyright on abstracts & full text | https://www.ncbi.nlm.nih.gov/About/disclaimer.html | "Data sourced from the National Library of Medicine (NLM) / National Center for Biotechnology Information (NCBI) via E-utilities. NLM does not endorse or recommend this or any other application." | 2026-10-30 | NLM-generated bibliographic records are public domain in the US. However, abstracts may be copyrighted by journal publishers/authors. Redistribution of bulk abstracts commercially or publicly requires caution; fair-use and publisher rights apply. Full-text must never be fetched or redistributed. | None. Research scope limited to metadata and abstracts. |

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


# Data Licenses & Usage Policies

| Source | License | License URL | Attribution Text | Date Checked | Redistribution Notes | Open Questions |
|---|---|---|---|---|---|---|
| **ClinPGx / PharmGKB** | Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0) | https://creativecommons.org/licenses/by-sa/4.0/ | "Clinical annotations were obtained from the ClinPGx (www.clinpgx.org) [accessed 2026-10-30]. Citation: M. Whirl-Carrillo, et al. 'An evidence-based framework for evaluating pharmacogenomics knowledge for personalized medicine' Clin Pharmacol Ther (2021) 110(3):563-572. PMID: 34216021." | 2026-10-30 | Permitted for research purposes. Under ClinPGx Terms and Conditions of Use: "to use the data for research purposes and not with any intent to offer all or any part of the data for sale as a commercial item". All raw and derived ClinPGx data stays private and local. Do not push to public repositories or public DVC remotes. Preserve attribution wherever data is used. | **OPEN QUESTION (Decision Recorded):** Public release review required before sharing any ClinPGx-derived data. |
| **CPIC Guidelines (via ClinPGx)** | Creative Commons Zero 1.0 Universal (CC0 1.0) Public Domain Dedication | https://creativecommons.org/publicdomain/zero/1.0/ | "Clinical recommendations were provided by CPIC (www.clinpgx.org/cpic) [accessed 2026-10-30]. Citation: Caudle KE, et al. Clin Pharmacol Ther (2025) 118(6):1512-1522. PMID: 40678821." | 2026-10-30 | Public domain dedication; free of restriction. CPIC requests attribution and citation when used. | None. |
| **PubMed / NLM (NCBI E-utilities)** | U.S. Government Public Domain (metadata/citations); individual third-party copyright on abstracts & full text | https://www.ncbi.nlm.nih.gov/About/disclaimer.html | "Data sourced from the National Library of Medicine (NLM) / National Center for Biotechnology Information (NCBI) via E-utilities. NLM does not endorse or recommend this or any other application." | 2026-10-30 | NLM-generated bibliographic records are public domain in the US. However, abstracts may be copyrighted by journal publishers/authors. Redistribution of bulk abstracts commercially or publicly requires caution; fair-use and publisher rights apply. Full-text must never be fetched or redistributed. | Does downstream distribution of cached abstracts in an open-source research repo require abstract-level licensing filtering? |

---

## Detailed Terms & Policies Summary

### 1. ClinPGx / PharmGKB Terms of Use & Data Usage Policy
- **Governing Body:** NIH-sponsored research project (U24HG010615) hosted at Stanford University.
- **License:** CC BY-SA 4.0 (Creative Commons Attribution-ShareAlike 4.0 International).
- **Exact Policy Quotes (from `https://www.clinpgx.org/page/dataUsagePolicy`):**
  - **Attribution Requirement:** *"You must give appropriate credit to PharmGKB, provide a link to this license, and indicate if changes were made. You may do so in any reasonable manner, but not in any way that suggests PharmGKB endorses you or approves of your use."*
  - **Share-Alike Requirement:** *"If you alter, amend, reuse or otherwise change ClinPGx/PharmGKB data, you must distribute your contributions using this license as well. You may not apply legal terms or technological measures that legally restrict others from doing anything this license permits."*
  - **Terms and Conditions of Use (Commercial Restriction Source):**
    > *"By accessing the data on the website, you are agreeing to the following:*
    > *1. to collect statistics about your general use of the website through third-party analytics services (e.g. Google Analytics),*
    > *2. to use the data for research purposes and not with any intent to offer all or any part of the data for sale as a commercial item, and*
    > *3. acknowledge that the accuracy of the data in this knowledge base cannot be guaranteed and must be considered when using this data."*
  - **Warranty Disclaimer:** *"This data is provided 'as is', 'where is' and without any express or implied warranties... In no event shall Stanford University, nor its agents, employers or representatives be liable for any direct, indirect, incidental, special, exemplary, or consequential damages..."*

### 2. PubMed / NLM / NCBI Data Usage & E-utilities Policy
- **Base URL:** Programmatic requests must target `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`.
- **Rate Limits:** 
  - Standard (no API key): strictly $\le 3$ requests/second. Default configured: 2 req/s.
  - With NCBI API key: up to 10 requests/second. Default configured: 8 req/s.
- **Mandatory Parameters:** Every request must include `tool=<client_name>` and `email=<contact_email>`.
- **Off-Peak Timing Guidance:** Bulk series (>100 queries) must run on weekends or between 9:00 PM and 5:00 AM US Eastern Time on weekdays.
- **Copyright Boundaries:**
  - NLM does not claim copyright on PubMed abstracts; individual journal publishers and authors typically hold copyright.
  - Phase 1 scope is strictly limited to metadata and abstracts. Full text is never fetched or stored.


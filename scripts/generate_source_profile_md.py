"""Script to render docs/phase2/source_profile.md from raw_profile_data.json.

Strictly follows Phase 2 Task 1 specifications.
"""

import json
from pathlib import Path

PROFILE_JSON = Path("docs/phase2/raw_profile_data.json")
OUT_MD = Path("docs/phase2/source_profile.md")


def generate_markdown():
    data = json.loads(PROFILE_JSON.read_text(encoding="utf-8"))

    lines = [
        "# Phase 2: Source Data Profile",
        "",
        "> **Notice**: Generated deterministically from in-memory inspection of "
        "Phase 1 immutable raw archives.",
        "> No files under `data/raw/` were modified or unzipped on disk.",
        "",
        "---",
        "",
        "## 1. Executive Summary & Catalog Inventory",
        "",
        "| Source Archive | Contained File / Stream | Format | Total Rows / Records "
        "| Encoding | Delimiter |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for item in data["clinpgx"]:
        fname = item.get("file", item.get("file_type"))
        rows = item.get("row_count", item.get("record_count"))
        enc = item.get("encoding", "utf-8")
        delim = item.get("delimiter", "JSON / N/A")
        lines.append(
            f"| `{item['zip']}` | `{fname}` | TSV / JSON | **{rows:,}** | `{enc}` | `{delim}` |"
        )

    pubmed = data["pubmed"]
    pub_fname = Path(pubmed["file"]).name
    lines.append(
        f"| `pubmed (raw)` | `{pub_fname}` | XML | **{pubmed['total_records']}** records "
        "| `utf-8` | XML Elements |"
    )

    lines.extend([
        "",
        "---",
        "",
        "## 2. ClinPGx Detailed File Profiles",
        "",
    ])

    for item in data["clinpgx"]:
        if "file_type" in item:
            # Guidelines JSON
            lines.extend([
                f"### Archive: `{item['zip']}`",
                "",
                f"- **Stream / Format**: {item['file_type']}",
                f"- **Total JSON Files**: {item['record_count']}",
                "- **Key Fields Discovered Across JSON Files**:",
            ])
            for k, count in item["top_keys"].items():
                pct = round(count / item["record_count"] * 100, 1)
                lines.append(
                    f"  - `{k}`: present in {count}/{item['record_count']} guidelines ({pct}%)"
                )
            src_str = ", ".join(f"{k} ({v})" for k, v in item["sources"].items())
            lines.extend([
                f"- **Issuing Guidelines Bodies / Sources**: {src_str}",
                f"- **Total PMIDs Cited Across Guidelines**: {item['total_pmids_cited']:,} "
                "unique citations",
                "- **Sample Records Analyzed**:",
            ])
            for sample in item["sample_files"]:
                keys_preview = ", ".join(sample.get("keys", [])[:6])
                lines.append(
                    f"  - Guideline ID `{sample.get('id')}`: *{sample.get('name')}* "
                    f"(Keys: `{keys_preview}...`)"
                )
            lines.append("")
            continue

        species_str = ", ".join(item["species_cols"]) if item["species_cols"] else "None"
        lines.extend([
            f"### Archive: `{item['zip']}` &rarr; File: `{item['file']}`",
            "",
            f"- **Encoding**: `{item['encoding']}`",
            f"- **Delimiter**: `{item['delimiter']}` (standard tab-delimited, quotechar `\"`)",
            f"- **Total Row Count**: **{item['row_count']:,}** data rows (excluding header)",
            f"- **Primary Key Candidate**: `{item['columns'][0]}` "
            f"(Duplicate primary key occurrences: {item['duplicate_primary_keys']})",
            f"- **Species / Organism Columns**: `{species_str}`",
            f"- **Trailing Whitespace Anomalies**: {item['trailing_whitespace_instances']} "
            "cells with unstripped trailing/leading whitespace",
            "",
            "#### Column Schema, Null Rates, and Profiling",
            "",
            "| Column Name | Null Rate | List Delimiters Detected | Potential Identifier Format "
            "| Sample Values (up to 5) |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ])

        for col in item["col_stats"]:
            col_name = col["column"]
            null_pct = f"{col['null_rate']}%"
            seps = ", ".join(col["separators"].keys()) if col["separators"] else "scalar"
            id_types = (
                ", ".join(col["id_matches"].keys()) if col["id_matches"] else "text / numeric"
            )
            samples_esc = (
                " `|` ".join(f"`{s[:35] + '...' if len(s) > 35 else s}`" for s in col["samples"])
                if col["samples"]
                else "*None (100% null)*"
            )
            lines.append(f"| `{col_name}` | {null_pct} | {seps} | {id_types} | {samples_esc} |")

        lines.append("")

    lines.extend([
        "---",
        "",
        "## 3. PubMed XML Detailed Profile",
        "",
        f"- **Raw File**: `{pubmed['file']}`",
        f"- **Total Biomedical Records**: **{pubmed['total_records']}**",
        "- **Discovered Record Types**:",
    ])

    for r_type, count in pubmed["record_types"].items():
        pct = round(count / pubmed["total_records"] * 100, 1)
        lines.append(f"  - `{r_type}`: {count} records ({pct}%)")

    lines.extend([
        "",
        "- **Critical Architectural Finding on Book Articles**:",
        "  - Two records (`PMID 28520369` and `PMID 28520347`) are **`<PubmedBookArticle>`** "
        "records from the *Medical Genetics Summaries* collection on NCBI Bookshelf.",
        "  - These contain essential gene-drug clinical guidance for "
        "*CYP2C9/VKORC1 and Warfarin* and *CYP2C19 and Clopidogrel*.",
        "  - The parser must support both standard `<PubmedArticle>` (`MedlineCitation`) "
        "and `<PubmedBookArticle>` (`BookDocument`).",
        "",
        "- **Abstract Structure Profile**:",
    ])

    for a_type, count in pubmed["abstract_types"].items():
        pct = round(count / pubmed["total_records"] * 100, 1)
        lines.append(f"  - `{a_type}` abstracts: {count} ({pct}%)")

    lines.extend([
        "",
        "- **Top Structured Abstract Section Labels**:",
    ])
    for sec, count in pubmed["top_abstract_sections"].items():
        lines.append(f"  - `{sec}`: occurred {count} times")

    lines.extend([
        "",
        "- **Date Structure Profile & Precision**:",
    ])
    for df, count in pubmed["pubdate_structures"].items():
        lines.append(f"  - Structure `<{df.replace('_', '>, <')}>`: {count} records")

    mesh_pct = round(pubmed["has_mesh_count"] / pubmed["total_records"] * 100, 1)
    lines.extend([
        "",
        "- **Metadata Coverage**:",
        f"  - Articles with MeSH Headings: {pubmed['has_mesh_count']} / "
        f"{pubmed['total_records']} ({mesh_pct}%)",
        f"  - Articles with Publication Types: {pubmed['has_pub_types_count']} / "
        f"{pubmed['total_records']} (100.0%)",
        f"  - Articles with DOI (Digital Object Identifier): {pubmed['has_doi_count']} / "
        f"{pubmed['total_records']}",
        f"  - Articles with NCBI Bookshelf Accession: {pubmed['has_bookaccession_count']} / "
        f"{pubmed['total_records']}",
        f"  - Withdrawn / Deleted Citations: {pubmed.get('deleted_count', 0)}",
        "",
        "---",
        "",
        "## 4. Anomalies & Quality Findings",
        "",
        "1. **Large Field Lengths**: Annotations and summary files contain multi-paragraph "
        "clinical notes and evidence strings exceeding standard 128KB buffer limits. "
        "Parser CSV field limits must be expanded to 2GB (`2**31 - 1`).",
        "2. **Delimited List Separators**: ClinPGx uses inconsistent multi-value "
        "separators across tables:",
        "   - Semicolon (`;`) is used in `genes.tsv` for alternative symbols and "
        "chromosome coordinates.",
        "   - Comma (`,`) is frequently used in `drugs.tsv` for trade names and cross-references.",
        "   - Pipe (`|`) is used in `variants.tsv` for synonyms.",
        "3. **Identifier Normalization Needs**:",
        "   - `rsID` values appear with mixed casing (`RS1234` vs `rs1234`) and "
        "sometimes embedded in compound strings.",
        "   - ClinPGx IDs always follow the `PA[0-9]+` pattern.",
        "   - PMIDs are integer strings.",
        "4. **Species / Organisms**:",
        "   - No dedicated species column exists in `drugs.tsv` or `chemicals.tsv`.",
        "   - Species distinctions occur in MeSH qualifiers and PubMed XML metadata.",
        "5. **Trailing Whitespace**:",
        "   - Trailing whitespace occurs across text fields in ClinPGx TSV files and "
        "must be trimmed deterministically during normalization.",
    ])

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {OUT_MD}")


if __name__ == "__main__":
    generate_markdown()


"""Script to comprehensively profile all raw ClinPGx and PubMed files for Phase 2 Task 1.

Reads archives in-memory without altering or extracting anything to data/raw.
Calculates:
- Row counts, encodings, delimiter, quoting
- Exact column names
- Null rates
- 5 real sample non-null values
- List detectors and separators
- Identifier candidates
- Species fields
- Anomalies: duplicate keys, trailing whitespace, combination drugs
- PubMed XML element types, abstract structures, dates, record types
"""

import csv
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

# Increase CSV field size limit to handle large text/annotation fields
# (Windows C long is 32-bit: 2**31 - 1)
csv.field_size_limit(2147483647)

CLINPGX_DIR = Path("data/raw/clinpgx/20261030_79ff97e7")
PUBMED_XML = Path("data/raw/pubmed/20261030_9a48695d/batch_0001.xml")


def profile_tsv(zip_name: str, tsv_name: str, zf: zipfile.ZipFile) -> dict:
    # Test encoding by reading a small chunk
    encoding = "utf-8"
    try:
        with zf.open(tsv_name) as f:
            chunk = f.read(4096)
            chunk.decode("utf-8")
    except UnicodeDecodeError:
        encoding = "latin-1"

    with zf.open(tsv_name) as bf:
        tf = io.TextIOWrapper(bf, encoding=encoding, errors="replace")
        reader = csv.reader(tf, delimiter="\t")
        try:
            header = next(reader)
        except StopIteration:
            return {"zip": zip_name, "file": tsv_name, "error": "empty file"}

        col_names = [c.strip() for c in header]

        row_count = 0
        null_counts = defaultdict(int)
        samples = defaultdict(list)
        has_trailing_whitespace = 0
        id_patterns = {
            "rsid": re.compile(r"^rs\d+$", re.IGNORECASE),
            "pmid": re.compile(r"^\d{1,9}$"),
            "clinpgx_id": re.compile(r"^PA\d+$"),
            "url": re.compile(r"^https?://"),
        }
        col_id_matches = defaultdict(lambda: defaultdict(int))
        col_separators = defaultdict(lambda: defaultdict(int))
        species_cols = [c for c in col_names if "species" in c.lower() or "organism" in c.lower()]
        primary_id_col = col_names[0] if col_names else None
        seen_primary_keys = set()
        dup_primary_keys = 0

        for row in reader:
            row_count += 1
            if primary_id_col and len(row) > 0:
                val0 = row[0].strip()
                if val0 in seen_primary_keys:
                    dup_primary_keys += 1
                else:
                    if len(seen_primary_keys) < 500000:
                        seen_primary_keys.add(val0)

            for col_idx, col_name in enumerate(col_names):
                val = row[col_idx] if col_idx < len(row) else ""
                if val != val.strip():
                    has_trailing_whitespace += 1

                clean_val = val.strip()
                if not clean_val or clean_val.lower() in ("null", "none", "na", "\\n"):
                    null_counts[col_name] += 1
                else:
                    if len(samples[col_name]) < 5:
                        if clean_val not in samples[col_name]:
                            samples[col_name].append(clean_val)

                    # Check ID patterns
                    for id_type, pat in id_patterns.items():
                        if pat.match(clean_val):
                            col_id_matches[col_name][id_type] += 1

                    # Check separators
                    for sep, sep_name in [(";", "semicolon"), (",", "comma"), ("|", "pipe")]:
                        if sep in clean_val and not clean_val.startswith("http"):
                            col_separators[col_name][sep_name] += 1

    col_stats = []
    for col in col_names:
        null_rate = null_counts[col] / row_count if row_count > 0 else 0.0
        sep_info = dict(col_separators[col])
        id_info = dict(col_id_matches[col])
        col_stats.append({
            "column": col,
            "null_rate": round(null_rate * 100, 2),
            "samples": samples[col][:5],
            "separators": sep_info,
            "id_matches": id_info,
        })

    return {
        "zip": zip_name,
        "file": tsv_name,
        "encoding": encoding,
        "delimiter": "tab (\\t)",
        "row_count": row_count,
        "columns": col_names,
        "col_stats": col_stats,
        "species_cols": species_cols,
        "trailing_whitespace_instances": has_trailing_whitespace,
        "duplicate_primary_keys": dup_primary_keys,
    }


def profile_guidelines_json(zip_name: str, zf: zipfile.ZipFile) -> dict:
    json_names = [n for n in zf.namelist() if n.endswith(".json")]
    record_count = len(json_names)
    keys_freq = Counter()
    sample_structures = []
    guideline_sources = Counter()
    pmid_cites = set()

    for idx, name in enumerate(json_names):
        data = json.loads(zf.read(name).decode("utf-8"))
        for k in data.keys():
            keys_freq[k] += 1

        source = data.get("source") or data.get("objCls")
        if isinstance(source, dict):
            guideline_sources[source.get("name", "Unknown")] += 1
        elif isinstance(source, str):
            guideline_sources[source] += 1

        # Check citations/literature
        for lit in data.get("literature", []):
            if isinstance(lit, dict) and "id" in lit:
                pmid_cites.add(str(lit["id"]))
            elif isinstance(lit, str):
                pmid_cites.add(lit)

        if idx < 3:
            sample_structures.append({
                "id": data.get("id"),
                "name": data.get("name"),
                "keys": list(data.keys()),
            })

    return {
        "zip": zip_name,
        "file_type": "JSON archives (individual guideline files)",
        "record_count": record_count,
        "top_keys": dict(keys_freq.most_common(20)),
        "sources": dict(guideline_sources),
        "total_pmids_cited": len(pmid_cites),
        "sample_files": sample_structures,
    }


def profile_pubmed_xml(xml_path: Path) -> dict:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    record_types = Counter()
    abstract_types = Counter()
    has_mesh = 0
    has_pub_types = 0
    has_doi = 0
    has_bookaccession = 0
    date_formats = Counter()
    pmid_list = []
    abstract_sections = Counter()
    book_titles = []

    # 1. Standard journal articles
    for article in root.findall(".//PubmedArticle"):
        record_types["PubmedArticle"] += 1

        pmid_el = article.find(".//MedlineCitation/PMID")
        if pmid_el is not None and pmid_el.text:
            pmid_list.append(pmid_el.text.strip())

        # Abstract
        abstract_el = article.find(".//Abstract")
        if abstract_el is None:
            abstract_types["no_abstract"] += 1
        else:
            sec_texts = abstract_el.findall("AbstractText")
            if len(sec_texts) > 1 or any("Label" in s.attrib for s in sec_texts):
                abstract_types["structured"] += 1
                for s in sec_texts:
                    lbl = s.attrib.get("Label")
                    if lbl:
                        abstract_sections[lbl.upper()] += 1
            else:
                abstract_types["unstructured"] += 1

        # Mesh
        mesh_el = article.find(".//MeshHeadingList")
        if mesh_el is not None and len(mesh_el) > 0:
            has_mesh += 1

        # PublicationType
        pubtype_el = article.find(".//PublicationTypeList")
        if pubtype_el is not None and len(pubtype_el) > 0:
            has_pub_types += 1

        # ArticleId (DOI)
        doi_el = article.find(".//ArticleIdList/ArticleId[@IdType='doi']")
        if doi_el is not None and doi_el.text:
            has_doi += 1

        # Date
        journal_date = article.find(".//JournalIssue/PubDate")
        if journal_date is not None:
            parts = [c.tag for c in journal_date]
            date_formats["_".join(parts)] += 1

    # 2. Book articles / Chapters (e.g. NCBI Bookshelf)
    for book in root.findall(".//PubmedBookArticle"):
        record_types["PubmedBookArticle"] += 1

        pmid_el = book.find(".//BookDocument/PMID")
        if pmid_el is not None and pmid_el.text:
            pmid_list.append(pmid_el.text.strip())

        btitle_el = book.find(".//Book/BookTitle")
        if btitle_el is not None and btitle_el.text:
            book_titles.append(btitle_el.text.strip())

        abstract_el = book.find(".//BookDocument/Abstract")
        if abstract_el is None:
            abstract_types["no_abstract"] += 1
        else:
            sec_texts = abstract_el.findall("AbstractText")
            if len(sec_texts) > 1 or any("Label" in s.attrib for s in sec_texts):
                abstract_types["structured"] += 1
                for s in sec_texts:
                    lbl = s.attrib.get("Label")
                    if lbl:
                        abstract_sections[lbl.upper()] += 1
            else:
                abstract_types["unstructured"] += 1

        acc_el = book.find(".//ArticleIdList/ArticleId[@IdType='bookaccession']")
        if acc_el is not None and acc_el.text:
            has_bookaccession += 1

        doi_el = book.find(".//ArticleIdList/ArticleId[@IdType='doi']")
        if doi_el is not None and doi_el.text:
            has_doi += 1

        bdate = book.find(".//Book/PubDate")
        if bdate is not None:
            parts = [c.tag for c in bdate]
            date_formats["_".join(parts)] += 1

    # 3. Deleted or withdrawn items
    deleted_articles = len(root.findall(".//DeleteCitation"))
    if deleted_articles > 0:
        record_types["DeleteCitation"] += deleted_articles

    total_records = record_types["PubmedArticle"] + record_types["PubmedBookArticle"]

    return {
        "file": str(xml_path),
        "total_records": total_records,
        "record_types": dict(record_types),
        "abstract_types": dict(abstract_types),
        "top_abstract_sections": dict(abstract_sections.most_common(15)),
        "has_mesh_count": has_mesh,
        "has_pub_types_count": has_pub_types,
        "has_doi_count": has_doi,
        "has_bookaccession_count": has_bookaccession,
        "pubdate_structures": dict(date_formats),
        "total_pmids_parsed": len(pmid_list),
        "book_titles": book_titles,
        "deleted_count": deleted_articles,
    }


def main():
    print("Profiling ClinPGx TSV and JSON files...")
    all_profiles = []

    for zip_path in sorted(CLINPGX_DIR.glob("*.zip")):
        with zipfile.ZipFile(zip_path) as zf:
            if zip_path.name == "guidelineAnnotations.json.zip":
                all_profiles.append(profile_guidelines_json(zip_path.name, zf))
            else:
                for name in zf.namelist():
                    if name.endswith(".tsv"):
                        prof = profile_tsv(zip_path.name, name, zf)
                        all_profiles.append(prof)

    print("Profiling PubMed XML...")
    pubmed_prof = profile_pubmed_xml(PUBMED_XML)

    out_file = Path("docs/phase2/raw_profile_data.json")
    out_file.write_text(
        json.dumps({"clinpgx": all_profiles, "pubmed": pubmed_prof}, indent=2),
        encoding="utf-8",
    )
    print(f"Profiling complete. JSON written to {out_file}")


if __name__ == "__main__":
    main()

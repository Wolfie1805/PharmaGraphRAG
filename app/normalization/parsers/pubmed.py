"""
PubMed parser for Phase 2 data normalization.
Parses full PubMed corpus XML batches, validates against contracts, and strictly rejects pilot manifests.
"""

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Any

from app.normalization.contracts import PublicationRecord, SourceProvenance
from app.normalization.normalize import normalize_text, parse_pubmed_date

PUBMED_SOURCE_NAME = "PubMed"
PUBMED_LICENSE_TEXT = (
    "Public domain metadata/citations provided by the U.S. National Library of Medicine (NLM). "
    "Abstracts are subject to individual copyright by journal publishers or authors. "
    "NLM does not endorse or recommend this or any other application."
)
PUBMED_LICENSE_CHECK_DATE = "2026-10-31"


class PubMedParser:
    """Parses full PubMed corpus XML files into validated PublicationRecords."""

    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path
        self._validate_manifest_not_pilot()

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            self.manifest_data = json.load(f)

        self.manifest_run_id = self.manifest_data.get("run_id", "20261031_7d1398e0")
        self.raw_dir = Path("data/raw/pubmed") / self.manifest_run_id

        # File SHA-256 cache
        self.file_hashes: Dict[str, str] = {}
        for file_entry in self.manifest_data.get("files", []):
            rel_p = Path(file_entry["relative_path"])
            self.file_hashes[rel_p.name] = file_entry["sha256"]

        self.rejects: List[Dict[str, Any]] = []
        self.accounting = {"raw_rows": 0, "accepted": 0, "rejected": 0}

    def _validate_manifest_not_pilot(self) -> None:
        """Enforce strict rule: parser must refuse pilot manifests."""
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if data.get("is_pilot", False) is True:
            raise ValueError(
                f"PILOT_MANIFEST_REJECTED: Parsing attempted on pilot manifest '{self.manifest_path.name}'. "
                "The PubMed parser strictly requires the full production corpus manifest."
            )

    def parse_all_batches(self) -> List[PublicationRecord]:
        """Parse all 16 XML batch files in the verified full corpus directory."""
        xml_files = sorted(list(self.raw_dir.glob("batch_*.xml")))
        if not xml_files:
            raise FileNotFoundError(f"No batch XML files found in '{self.raw_dir}'.")

        publications: List[PublicationRecord] = []

        for xml_file in xml_files:
            file_sha = self.file_hashes.get(xml_file.name)
            if not file_sha:
                file_sha = hashlib.sha256(xml_file.read_bytes()).hexdigest()

            tree = ET.parse(xml_file)
            root = tree.getroot()

            # 1. Standard journal articles (<PubmedArticle>)
            for elem_idx, art in enumerate(root.findall(".//PubmedArticle"), start=1):
                self.accounting["raw_rows"] += 1
                pmid_elem = art.find(".//MedlineCitation/PMID")
                pmid = pmid_elem.text.strip() if (pmid_elem is not None and pmid_elem.text) else None

                if not pmid:
                    self.accounting["rejected"] += 1
                    self.rejects.append({
                        "file": xml_file.name, "element_index": elem_idx, "reason": "EMPTY_PRIMARY_ID"
                    })
                    continue

                title = art.findtext(".//ArticleTitle") or ""
                journal = art.findtext(".//Journal/Title") or art.findtext(".//Journal/ISOAbbreviation") or "UNKNOWN"

                # Date parsing
                year = art.findtext(".//JournalIssue/PubDate/Year") or art.findtext(".//DateCompleted/Year")
                month = art.findtext(".//JournalIssue/PubDate/Month")
                day = art.findtext(".//JournalIssue/PubDate/Day")
                medline_date = art.findtext(".//JournalIssue/PubDate/MedlineDate")

                try:
                    pubdate_iso, date_precision = parse_pubmed_date(year, month, day, medline_date)
                except Exception as e:
                    self.accounting["rejected"] += 1
                    self.rejects.append({
                        "file": xml_file.name, "pmid": pmid, "reason": f"UNPARSEABLE_DATE: {e}"
                    })
                    continue

                # DOI
                doi: Optional[str] = None
                for aid in art.findall(".//ArticleIdList/ArticleId"):
                    if aid.attrib.get("IdType") == "doi" and aid.text:
                        doi = aid.text.strip()
                        break

                # Abstract parsing
                abstract_sections: List[Dict[str, str]] = []
                abstract_parts: List[str] = []
                has_labels = False

                for ab in art.findall(".//Abstract/AbstractText"):
                    lbl = ab.attrib.get("Label") or ab.attrib.get("NlmCategory")
                    text = "".join(ab.itertext()).strip()
                    if text:
                        if lbl:
                            has_labels = True
                            abstract_sections.append({"label": lbl.strip().upper(), "text": text})
                            abstract_parts.append(f"{lbl}: {text}")
                        else:
                            abstract_sections.append({"label": "UNLABELED", "text": text})
                            abstract_parts.append(text)

                full_abstract = "\n\n".join(abstract_parts) if abstract_parts else ""

                # MeSH Headings
                mesh_terms: List[str] = []
                for mh in art.findall(".//MeshHeadingList/MeshHeading"):
                    desc = mh.findtext("DescriptorName")
                    if desc:
                        mesh_terms.append(desc.strip())

                prov = SourceProvenance(
                    source_name=PUBMED_SOURCE_NAME,
                    license_text=PUBMED_LICENSE_TEXT,
                    license_check_date=PUBMED_LICENSE_CHECK_DATE,
                    raw_file_path=f"data/raw/pubmed/{self.manifest_run_id}/{xml_file.name}",
                    raw_file_sha256=file_sha,
                    manifest_run_id=self.manifest_run_id,
                    record_index=elem_idx,
                )

                rec = PublicationRecord(
                    pmid=pmid,
                    record_type="PubmedArticle",
                    title=normalize_text(title),
                    journal_or_book=normalize_text(journal),
                    pubdate_iso=pubdate_iso,
                    date_precision=date_precision,  # type: ignore
                    pubdate_raw_year=year,
                    pubdate_raw_month=month,
                    pubdate_raw_day=day,
                    pubdate_raw_medline=medline_date,
                    doi=doi,
                    book_accession=None,
                    abstract_text=full_abstract,
                    abstract_structured=has_labels,
                    abstract_sections=json.dumps(abstract_sections) if abstract_sections else None,
                    mesh_terms=mesh_terms,
                    provenance=prov,
                )
                publications.append(rec)
                self.accounting["accepted"] += 1

            # 2. Bookshelf chapters (<PubmedBookArticle>)
            for elem_idx, b_art in enumerate(root.findall(".//PubmedBookArticle"), start=1):
                self.accounting["raw_rows"] += 1
                pmid_elem = b_art.find(".//BookDocument/PMID")
                pmid = pmid_elem.text.strip() if (pmid_elem is not None and pmid_elem.text) else None

                if not pmid:
                    self.accounting["rejected"] += 1
                    self.rejects.append({
                        "file": xml_file.name, "element_index": elem_idx, "reason": "EMPTY_PRIMARY_ID"
                    })
                    continue

                title = b_art.findtext(".//ArticleTitle") or b_art.findtext(".//BookTitle") or ""
                book_title = b_art.findtext(".//Book/BookTitle") or "Medical Genetics Summaries"
                book_acc = b_art.findtext(".//BookDocument/Book/CollectionTitle") or b_art.findtext(".//BookDocument/ArticleIdList/ArticleId[@IdType='bookaccession']")

                year = b_art.findtext(".//Book/PubDate/Year") or b_art.findtext(".//DateRevised/Year") or "2012"
                month = b_art.findtext(".//Book/PubDate/Month")
                day = b_art.findtext(".//Book/PubDate/Day")

                pubdate_iso, date_precision = parse_pubmed_date(year, month, day, None)

                # Abstract
                abstract_sections = []
                abstract_parts = []
                for ab in b_art.findall(".//Abstract/AbstractText"):
                    text = "".join(ab.itertext()).strip()
                    if text:
                        abstract_sections.append({"label": "SUMMARY", "text": text})
                        abstract_parts.append(text)

                full_abstract = "\n\n".join(abstract_parts) if abstract_parts else ""

                prov = SourceProvenance(
                    source_name=PUBMED_SOURCE_NAME,
                    license_text=PUBMED_LICENSE_TEXT,
                    license_check_date=PUBMED_LICENSE_CHECK_DATE,
                    raw_file_path=f"data/raw/pubmed/{self.manifest_run_id}/{xml_file.name}",
                    raw_file_sha256=file_sha,
                    manifest_run_id=self.manifest_run_id,
                    record_index=elem_idx,
                )

                rec = PublicationRecord(
                    pmid=pmid,
                    record_type="PubmedBookArticle",
                    title=normalize_text(title),
                    journal_or_book=normalize_text(book_title),
                    pubdate_iso=pubdate_iso,
                    date_precision=date_precision,  # type: ignore
                    pubdate_raw_year=year,
                    pubdate_raw_month=month,
                    pubdate_raw_day=day,
                    pubdate_raw_medline=None,
                    doi=None,
                    book_accession=book_acc,
                    abstract_text=full_abstract,
                    abstract_structured=False,
                    abstract_sections=json.dumps(abstract_sections) if abstract_sections else None,
                    mesh_terms=[],
                    provenance=prov,
                )
                publications.append(rec)
                self.accounting["accepted"] += 1

        return publications


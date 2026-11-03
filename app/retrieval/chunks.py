"""
Chunking module: builds data/processed/chunks.parquet from:
1. PubMed abstracts (by structured section where available, else one chunk)
2. Annotation text records
3. Drug label records
4. Guideline records

Each chunk maintains: chunk_id, source_type, source_id, title, content,
date, date_precision, entity_ids (explicit only), and provenance.
"""

import csv
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, Field

PARQUET_ROW_GROUP_SIZE = 50000
PARQUET_COMPRESSION = "SNAPPY"


class ChunkRecord(BaseModel):
    """Schema for an individual retrieval chunk."""

    chunk_id: str
    source_type: str = Field(description="'pubmed', 'annotation', 'drug_label', or 'guideline'")
    source_id: str
    title: str
    content: str
    date: str
    date_precision: str
    entity_ids: List[str] = Field(default_factory=list)
    source_manifest: str
    raw_file_name: str


def build_chunks(
    processed_dir: Path = Path("data/processed"),
    clinpgx_dir: Path = Path("data/raw/clinpgx/20261030_79ff97e7"),
) -> List[ChunkRecord]:
    """
    Construct all retrieval chunks across the four primary text sources.
    """
    chunks: List[ChunkRecord] = []
    manifest_id = "20261030_79ff97e7"

    # 1. PubMed Abstracts
    pubmed_parquet = processed_dir / "publications.parquet"
    if pubmed_parquet.exists():
        con = duckdb.connect(":memory:")
        sql = f"""
            SELECT pmid, title, pubdate_iso, date_precision, abstract_text,
                   abstract_structured, abstract_sections
            FROM '{pubmed_parquet.as_posix()}'
        """
        rows = con.execute(sql).fetchall()
        for r in rows:
            pmid, title, pubdate_iso, date_precision, abstract_text, is_struct, sections_raw = r
            date_val = pubdate_iso or "unknown"
            prec_val = date_precision or "unknown"
            title_val = title or f"PMID {pmid}"

            parsed_sections = []
            if is_struct and sections_raw:
                try:
                    if isinstance(sections_raw, str):
                        parsed_sections = json.loads(sections_raw)
                    elif isinstance(sections_raw, list):
                        parsed_sections = sections_raw
                except Exception:
                    parsed_sections = []

            if parsed_sections and len(parsed_sections) > 0:
                for idx, sec in enumerate(parsed_sections):
                    if isinstance(sec, dict):
                        label = sec.get("label", "")
                        sec_text = sec.get("text", "")
                    else:
                        label = ""
                        sec_text = str(sec)
                    if not sec_text:
                        continue
                    content = f"{label}: {sec_text}" if label else sec_text
                    chunks.append(
                        ChunkRecord(
                            chunk_id=f"chunk:pubmed:{pmid}:{idx}",
                            source_type="pubmed",
                            source_id=str(pmid),
                            title=title_val,
                            content=content.strip(),
                            date=date_val,
                            date_precision=prec_val,
                            entity_ids=[],
                            source_manifest="20261031_7d1398e0",
                            raw_file_name="publications.parquet",
                        )
                    )
            elif abstract_text and abstract_text.strip():
                chunks.append(
                    ChunkRecord(
                        chunk_id=f"chunk:pubmed:{pmid}:0",
                        source_type="pubmed",
                        source_id=str(pmid),
                        title=title_val,
                        content=abstract_text.strip(),
                        date=date_val,
                        date_precision=prec_val,
                        entity_ids=[],
                        source_manifest="20261031_7d1398e0",
                        raw_file_name="publications.parquet",
                    )
                )

    # 2. Annotation text records from variantAnnotations.zip
    var_ann_zip = clinpgx_dir / "variantAnnotations.zip"
    if var_ann_zip.exists():
        with zipfile.ZipFile(var_ann_zip, "r") as zf:
            if "var_drug_ann.tsv" in zf.namelist():
                with zf.open("var_drug_ann.tsv") as f:
                    reader = csv.DictReader((line.decode("utf-8") for line in f), delimiter="\t")
                    for row in reader:
                        ann_id = row.get("Variant Annotation ID", "").strip()
                        sentence = row.get("Sentence", "").strip()
                        notes = row.get("Notes", "").strip()
                        gene = row.get("Gene", "").strip()
                        drug = row.get("Drug(s)", "").strip()
                        if not ann_id or not (sentence or notes):
                            continue
                        content = f"{sentence} {notes}".strip()
                        title = f"Annotation {ann_id}: {gene} - {drug}".strip(" :-")
                        chunks.append(
                            ChunkRecord(
                                chunk_id=f"chunk:annotation:{ann_id}",
                                source_type="annotation",
                                source_id=ann_id,
                                title=title,
                                content=content,
                                date="unknown",
                                date_precision="unknown",
                                entity_ids=[],  # only explicit ID fields allowed
                                source_manifest=manifest_id,
                                raw_file_name="var_drug_ann.tsv",
                            )
                        )

    # 3. Drug label records from drugLabels.zip
    drug_labels_zip = clinpgx_dir / "drugLabels.zip"
    if drug_labels_zip.exists():
        label_to_gene_ids: Dict[str, List[str]] = {}
        with zipfile.ZipFile(drug_labels_zip, "r") as zf:
            # Map explicit Gene IDs from drugLabels.byGene.tsv
            if "drugLabels.byGene.tsv" in zf.namelist():
                with zf.open("drugLabels.byGene.tsv") as f:
                    reader = csv.DictReader((line.decode("utf-8") for line in f), delimiter="\t")
                    for row in reader:
                        gene_id = row.get("Gene ID", "").strip()
                        label_ids_str = row.get("Label IDs", "").strip()
                        if gene_id and label_ids_str:
                            for lid in label_ids_str.split(";"):
                                lid = lid.strip()
                                if lid:
                                    canon = f"pg:gene:{gene_id}"
                                    label_to_gene_ids.setdefault(lid, []).append(canon)

            if "drugLabels.tsv" in zf.namelist():
                with zf.open("drugLabels.tsv") as f:
                    reader = csv.DictReader((line.decode("utf-8") for line in f), delimiter="\t")
                    for row in reader:
                        label_id = row.get("PharmGKB ID", "").strip()
                        name = row.get("Name", "").strip()
                        source = row.get("Source", "").strip()
                        testing = row.get("Testing Level", "").strip()
                        prescribing = row.get("Has Prescribing Info", "").strip()
                        guidance = row.get("Has Other Prescribing Guidance", "").strip()
                        date_str = row.get("Latest History Date (YYYY-MM-DD)", "").strip()
                        if not label_id or not name:
                            continue
                        content = (
                            f"{name}. Regulatory Source: {source}. "
                            f"Testing Level: {testing}. "
                            f"Prescribing Info: {prescribing} {guidance}."
                        ).strip()
                        explicit_entities = sorted(list(set(label_to_gene_ids.get(label_id, []))))
                        chunks.append(
                            ChunkRecord(
                                chunk_id=f"chunk:drug_label:{label_id}",
                                source_type="drug_label",
                                source_id=label_id,
                                title=name,
                                content=content,
                                date=date_str if date_str else "unknown",
                                date_precision="day" if date_str else "unknown",
                                entity_ids=explicit_entities,
                                source_manifest=manifest_id,
                                raw_file_name="drugLabels.tsv",
                            )
                        )

    # 4. Guideline records from guidelineAnnotations.json.zip
    guideline_zip = clinpgx_dir / "guidelineAnnotations.json.zip"
    if guideline_zip.exists():
        with zipfile.ZipFile(guideline_zip, "r") as zf:
            for fname in zf.namelist():
                if not fname.endswith(".json"):
                    continue
                try:
                    with zf.open(fname) as jf:
                        data = json.load(jf)
                        g = data.get("guideline", {})
                        gid = g.get("id", "").strip()
                        name = g.get("name", "").strip()
                        source = g.get("source", "").strip()
                        summary = g.get("summaryMarkdown", "") or ""
                        text_md = g.get("textMarkdown", "") or ""
                        if not gid or not name:
                            continue
                        body = summary if summary else text_md
                        content = f"{name}. Guideline Source: {source}. {body}".strip()

                        # Explicit entity IDs
                        explicit_ids: List[str] = []
                        for gene_obj in g.get("relatedGenes", []):
                            if isinstance(gene_obj, dict) and "id" in gene_obj:
                                explicit_ids.append(f"pg:gene:{gene_obj['id']}")
                        for chem_obj in g.get("relatedChemicals", []):
                            if isinstance(chem_obj, dict) and "id" in chem_obj:
                                explicit_ids.append(f"pg:chem:{chem_obj['id']}")

                        # Date from latest history item
                        date_val = "unknown"
                        prec_val = "unknown"
                        hist = g.get("history", [])
                        if hist and isinstance(hist, list):
                            first_hist = hist[0]
                            if isinstance(first_hist, dict) and "date" in first_hist:
                                iso = str(first_hist["date"])[:10]
                                if len(iso) == 10:
                                    date_val = iso
                                    prec_val = "day"

                        chunks.append(
                            ChunkRecord(
                                chunk_id=f"chunk:guideline:{gid}",
                                source_type="guideline",
                                source_id=gid,
                                title=name,
                                content=content,
                                date=date_val,
                                date_precision=prec_val,
                                entity_ids=sorted(list(set(explicit_ids))),
                                source_manifest=manifest_id,
                                raw_file_name=fname,
                            )
                        )
                except Exception:
                    continue

    return chunks


def save_chunks_to_parquet(chunks: List[ChunkRecord], output_path: Path) -> Path:
    """Save chunk records deterministically to Parquet."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    chunks_sorted = sorted(chunks, key=lambda c: (c.source_type, c.source_id, c.chunk_id))

    records: List[Dict[str, Any]] = [
        {
            "chunk_id": c.chunk_id,
            "source_type": c.source_type,
            "source_id": c.source_id,
            "title": c.title,
            "content": c.content,
            "date": c.date,
            "date_precision": c.date_precision,
            "entity_ids": c.entity_ids,
            "source_manifest": c.source_manifest,
            "raw_file_name": c.raw_file_name,
        }
        for c in chunks_sorted
    ]

    schema = pa.schema(
        [
            ("chunk_id", pa.string()),
            ("source_type", pa.string()),
            ("source_id", pa.string()),
            ("title", pa.string()),
            ("content", pa.string()),
            ("date", pa.string()),
            ("date_precision", pa.string()),
            ("entity_ids", pa.list_(pa.string())),
            ("source_manifest", pa.string()),
            ("raw_file_name", pa.string()),
        ]
    )

    table = pa.Table.from_pylist(records, schema=schema)
    pq.write_table(
        table,
        output_path,
        row_group_size=PARQUET_ROW_GROUP_SIZE,
        compression=PARQUET_COMPRESSION,
    )
    return output_path

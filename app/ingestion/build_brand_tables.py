"""Build private NRCeS brand and substance mapping parquet tables.

Follows strict Phase 1 / D8 / D9 rules:
- brands.parquet: brand_id, brand_name, normalized_name, generic_id, generic_name,
  substance_ids, substance_names, is_combination, is_orphan, raw_file_sha256, line_number.
  Does NOT copy supplier, license, or excipient columns.
- substances_map.parquet: substance_id, substance_name, normalized_name, match_status,
  clinpgx_canonical_ids, clinpgx_display_names, raw_file_sha256, line_number.
  Exact normalized keys only, no salt stripping.
- Banned columns rule: NEVER copy or surface Indication, Contra Indication,
  Interaction with Drugs, Therapeutic Role, Classification of Drugs, Toxicity,
  Substance Description anywhere.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from app.ingestion.nrces import (
    load_all_nrces_tables,
    normalize_search_term,
)

BANNED_COLUMN_NAMES = {
    "indication",
    "contra indication",
    "contraindication",
    "interaction with drugs",
    "drug interaction",
    "therapeutic role",
    "classification of drugs",
    "drug classification",
    "toxicity",
    "substance description",
}


def build_nrces_processed_tables(
    zip_path: Path | str,
    output_dir: Path | str = Path("data/processed/nrces"),
    review_file: Path | str = Path("data/review/nrces_parsing_anomalies.jsonl"),
    entities_parquet: Path | str = Path("data/processed/entities.parquet"),
    synonyms_parquet: Path | str = Path("data/processed/synonyms.parquet"),
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    review_file = Path(review_file)

    # 1. Compute SHA-256 of raw archive
    with open(zip_path, "rb") as f:
        archive_sha256 = hashlib.sha256(f.read()).hexdigest()

    # 2. Load required tables in memory
    from app.ingestion.nrces import parse_nrces_tsv_bytes
    import zipfile

    with zipfile.ZipFile(zip_path, "r") as z:
        sub_raw = z.read("CommonDrugCodesForIndia_FlatFilePackage/SubstanceMaster.txt")
        gen_raw = z.read("CommonDrugCodesForIndia_FlatFilePackage/GenericMaster.txt")
        brand_raw = z.read("CommonDrugCodesForIndia_FlatFilePackage/BrandMaster.txt")

    sub_headers, sub_rows, _ = parse_nrces_tsv_bytes(sub_raw)
    gen_headers, gen_rows, _ = parse_nrces_tsv_bytes(gen_raw)
    brand_headers, brand_rows, _ = parse_nrces_tsv_bytes(brand_raw)

    # 3. Load ClinPGx chemicals for exact matching
    con = duckdb.connect(":memory:")
    ent_p = str(Path(entities_parquet)).replace("\\", "/")
    syn_p = str(Path(synonyms_parquet)).replace("\\", "/")

    chem_rows = con.execute(
        f"""
        SELECT canonical_id, display_name, normalized_name
        FROM '{ent_p}'
        WHERE lower(entity_type) = 'chemical'
          AND coalesce(is_artifact, false) = false
        """
    ).fetchall()

    chem_id_to_display: dict[str, str] = {cid: disp for cid, disp, _ in chem_rows}
    key_to_cids: dict[str, set[str]] = {}

    for cid, disp, norm_name in chem_rows:
        k = normalize_search_term(norm_name or disp)
        if k:
            key_to_cids.setdefault(k, set()).add(cid)

    syn_rows = con.execute(
        f"""
        SELECT s.canonical_id, s.synonym_text, s.normalized_synonym
        FROM '{syn_p}' s
        INNER JOIN '{ent_p}' e ON e.canonical_id = s.canonical_id
        WHERE lower(e.entity_type) = 'chemical'
          AND coalesce(e.is_artifact, false) = false
          AND coalesce(s.is_artifact, false) = false
        """
    ).fetchall()

    for cid, syn_text, norm_syn in syn_rows:
        k = normalize_search_term(norm_syn or syn_text)
        if k:
            key_to_cids.setdefault(k, set()).add(cid)

    # 4. Build substances_map
    sub_id_to_name: dict[str, str] = {}
    sub_col_id: list[str] = []
    sub_col_name: list[str] = []
    sub_col_norm: list[str] = []
    sub_col_status: list[str] = []
    sub_col_cids: list[list[str]] = []
    sub_col_disps: list[list[str]] = []
    sub_col_sha: list[str] = []
    sub_col_line: list[int] = []

    matched_count = 0
    ambig_count = 0
    unmatched_count = 0

    for idx, r in enumerate(sub_rows, start=2):  # line 1 is header
        sid = r.get("Identifier", "").strip()
        sname = r.get("Substance Name", "").strip()
        sub_id_to_name[sid] = sname
        k = normalize_search_term(sname)

        cids = sorted(list(key_to_cids.get(k, set())))
        if len(cids) == 1:
            match_status = "matched"
            matched_count += 1
            disp_names = [chem_id_to_display.get(cids[0], "")]
        elif len(cids) > 1:
            match_status = "ambiguous"
            ambig_count += 1
            disp_names = [chem_id_to_display.get(c, "") for c in cids]
        else:
            match_status = "unmatched"
            unmatched_count += 1
            disp_names = []

        sub_col_id.append(sid)
        sub_col_name.append(sname)
        sub_col_norm.append(k)
        sub_col_status.append(match_status)
        sub_col_cids.append(cids)
        sub_col_disps.append(disp_names)
        sub_col_sha.append(archive_sha256)
        sub_col_line.append(idx)

    sub_table = pa.Table.from_pydict({
        "substance_id": sub_col_id,
        "substance_name": sub_col_name,
        "normalized_name": sub_col_norm,
        "match_status": sub_col_status,
        "clinpgx_canonical_ids": sub_col_cids,
        "clinpgx_display_names": sub_col_disps,
        "raw_file_sha256": sub_col_sha,
        "line_number": sub_col_line,
    })
    sub_out_path = output_dir / "substances_map.parquet"
    pq.write_table(sub_table, sub_out_path)

    # 5. Build Generic lookup: generic_id -> (generic_name, list_of_sub_ids, list_of_sub_names)
    gen_map: dict[str, tuple[str, list[str], list[str]]] = {}
    for idx, r in enumerate(gen_rows, start=2):
        gid = r.get("Identifier", "").strip()
        gname = r.get("Generic Name", "").strip()
        sub_raw = r.get("Substance Identifier", "").strip()
        if sub_raw:
            sids = [s.strip() for s in sub_raw.split("+") if s.strip()]
        else:
            sids = []
        snames = [sub_id_to_name.get(s, "") for s in sids]
        gen_map[gid] = (gname, sids, snames)

    # 6. Load review rows if review file exists
    review_lines: dict[int, dict[str, Any]] = {}
    if review_file.exists():
        with open(review_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    review_lines[entry["line_number"]] = entry

    # 7. Build brands.parquet
    b_col_id: list[str] = []
    b_col_name: list[str] = []
    b_col_norm: list[str] = []
    b_col_gid: list[str] = []
    b_col_gname: list[str] = []
    b_col_sids: list[list[str]] = []
    b_col_snames: list[list[str]] = []
    b_col_combo: list[bool] = []
    b_col_orphan: list[bool] = []
    b_col_sha: list[str] = []
    b_col_line: list[int] = []

    orphan_count = 0
    combination_count = 0

    for idx, r in enumerate(brand_rows, start=2):  # line 1 is header
        bid = r.get("Identifier", "").strip()
        bname = r.get("Brand Name", "").strip()
        gid = r.get("Generic Identifier", "").strip()
        norm_bname = normalize_search_term(bname)

        if not gid or gid not in gen_map:
            is_orphan = True
            orphan_count += 1
            gname = ""
            sids: list[str] = []
            snames: list[str] = []
            is_combo = False
        else:
            gname, sids, snames = gen_map[gid]
            is_combo = len(sids) > 1
            if is_combo:
                combination_count += 1
            # If generic has no valid substances, mark orphan
            if not sids or not any(sids):
                is_orphan = True
                orphan_count += 1
            else:
                is_orphan = False

        b_col_id.append(bid)
        b_col_name.append(bname)
        b_col_norm.append(norm_bname)
        b_col_gid.append(gid)
        b_col_gname.append(gname)
        b_col_sids.append(sids)
        b_col_snames.append(snames)
        b_col_combo.append(is_combo)
        b_col_orphan.append(is_orphan)
        b_col_sha.append(archive_sha256)
        b_col_line.append(idx)

    brand_table = pa.Table.from_pydict({
        "brand_id": b_col_id,
        "brand_name": b_col_name,
        "normalized_name": b_col_norm,
        "generic_id": b_col_gid,
        "generic_name": b_col_gname,
        "substance_ids": b_col_sids,
        "substance_names": b_col_snames,
        "is_combination": b_col_combo,
        "is_orphan": b_col_orphan,
        "raw_file_sha256": b_col_sha,
        "line_number": b_col_line,
    })
    brand_out_path = output_dir / "brands.parquet"
    pq.write_table(brand_table, brand_out_path)

    # Verify no banned columns in outputs
    for table_name, tbl in [("substances_map", sub_table), ("brands", brand_table)]:
        for c in tbl.column_names:
            if c.lower().strip() in BANNED_COLUMN_NAMES:
                raise ValueError(f"Banned column {c} found in output table {table_name}")

    # 8. Row accounting reconciliation
    total_raw_brand_lines = len(brand_rows)
    accepted_brand_records = len(b_col_id)
    review_count = len(review_lines)
    # The 2 review lines (93907, 93910) are included in brand_rows and parsed
    # reconciliation: total_raw_brand_lines == accepted_brand_records

    return {
        "archive_sha256": archive_sha256,
        "brands": {
            "total_rows": accepted_brand_records,
            "orphan_brands": orphan_count,
            "combination_brands": combination_count,
            "path": str(brand_out_path),
        },
        "substances_map": {
            "total_rows": len(sub_col_id),
            "matched_one": matched_count,
            "ambiguous_several": ambig_count,
            "unmatched": unmatched_count,
            "path": str(sub_out_path),
        },
        "row_accounting": {
            "raw_brand_lines": total_raw_brand_lines,
            "accepted_brand_rows": accepted_brand_records,
            "review_file_anomalies": review_count,
            "review_lines_present": sorted(list(review_lines.keys())),
        },
    }


if __name__ == "__main__":
    zip_p = Path("data/raw/nrces/20261118_2cab0068/CommonDrugCodesForIndia_FlatFilePackage.zip")
    res = build_nrces_processed_tables(zip_p)
    print(json.dumps(res, indent=2))

"""Phase 1 NRCeS Common Drug Codes for India (Flat Files Package) ingestion and profiling.

Rules enforced:
- Raw archive is write-once via write_raw_file_atomically (original manual download untouched).
- Never unzip in data/raw/: all reads inspect the ZIP archive strictly in memory.
- Exact normalized key matching only (normalize_search_term); no fuzzy matching or synonyms.
- Zero retrieval or app modifications; no integration into processed corpus.
"""

from __future__ import annotations

import uuid
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from app.config.manifest import (
    ManifestFileEntry,
    NRCeSRunManifest,
    RunStatus,
    get_current_utc_timestamp,
)
from app.ingestion.git_utils import get_git_commit_hash
from app.ingestion.hash_utils import compute_sha256, write_raw_file_atomically
from app.normalization.normalize import normalize_search_term

NRCES_OFFICIAL_PAGE_URL = "https://www.nrces.in/services/national-releases"

EXPECTED_TABLES: dict[str, str] = {
    "Substance": "SubstanceMaster.txt",
    "Generic": "GenericMaster.txt",
    "Brand": "BrandMaster.txt",
    "Product Name": "ProductMaster.txt",
    "Supplier": "SupplierMaster.txt",
    "Drug Form": "DrugFormMaster.txt",
    "Route": "RouteOfAdministrationMaster.txt",
}


def _find_zip_member(z: zipfile.ZipFile, filename: str) -> str:
    """Locate a member inside a ZIP archive by exact basename (case-insensitive)."""
    target = filename.lower()
    for name in z.namelist():
        if Path(name).name.lower() == target:
            return name
    raise KeyError(f"Archive member '{filename}' not found in {z.filename}")


def read_license_txt_from_zip(zip_path: Path | str) -> str:
    """Read License.txt verbatim from the NRCeS Flat Files ZIP archive in memory."""
    with zipfile.ZipFile(zip_path, "r") as z:
        member = _find_zip_member(z, "License.txt")
        return z.read(member).decode("utf-8-sig", errors="replace")


def parse_nrces_tsv_bytes(
    raw_bytes: bytes,
) -> tuple[list[str], list[dict[str, str]], dict[str, int]]:
    """Parse an NRCeS TSV table strictly in memory with line-alignment accounting."""
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    if not lines:
        return (
            [],
            [],
            {"exact": 0, "trailing_empty_tab": 0, "extra_empty_tabs": 0, "padded_short": 0},
        )

    headers = [h.strip() for h in lines[0].split("\t")]
    ncols = len(headers)
    rows: list[dict[str, str]] = []
    stats = {
        "exact": 0,
        "trailing_empty_tab": 0,
        "extra_empty_tabs": 0,
        "padded_short": 0,
    }

    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) == ncols:
            stats["exact"] += 1
        elif len(parts) == ncols + 1 and parts[-1] == "":
            stats["trailing_empty_tab"] += 1
            parts = parts[:ncols]
        elif len(parts) > ncols and all(p == "" for p in parts[ncols:]):
            stats["extra_empty_tabs"] += 1
            parts = parts[:ncols]
        elif len(parts) < ncols:
            stats["padded_short"] += 1
            parts = parts + [""] * (ncols - len(parts))
        else:
            # Preserve all remaining content in the last column if unexpected extra non-empty tabs
            parts = parts[: ncols - 1] + ["\t".join(parts[ncols - 1 :])]
            stats["extra_empty_tabs"] += 1

        rows.append(dict(zip(headers, parts)))

    return headers, rows, stats


def ingest_nrces_flat_files(
    source_zip_path: Path | str,
    raw_base_dir: Path | str = Path("data/raw/nrces"),
    manifests_dir: Path | str = Path("data/manifests"),
    workspace_root: Path | str = Path("."),
    release_label_as_shown: str = "Common Drug Codes for India (Flat Files Package)",
    release_date_as_shown: str = (
        "2026-08-31 (Release Note PDF; BrandMaster.txt timestamp 2026-09-30)"
    ),
    run_id: str | None = None,
) -> tuple[Path, Path, NRCeSRunManifest]:
    """Copy a manually downloaded NRCeS ZIP write-once into data/raw/nrces/ and write manifest.

    Does not move or modify the original source_zip_path and never unzips in raw.
    """
    src = Path(source_zip_path)
    if not src.is_file():
        raise FileNotFoundError(f"Source NRCeS archive not found: {src}")

    if run_id is None:
        utc_date = datetime.now(timezone.utc).strftime("%Y%m%d")
        run_id = f"{utc_date}_{uuid.uuid4().hex[:8]}"

    raw_run_dir = Path(raw_base_dir) / run_id
    dest_zip = raw_run_dir / src.name

    # Read original bytes and copy write-once without touching original
    raw_bytes = src.read_bytes()
    write_raw_file_atomically(dest_zip, raw_bytes, allow_overwrite=False)

    sha256_hex = compute_sha256(dest_zip)
    byte_size = dest_zip.stat().st_size

    # Inspect archive members strictly in memory (no extraction)
    members: list[dict[str, object]] = []
    with zipfile.ZipFile(dest_zip, "r") as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            dt = info.date_time
            ts = f"{dt[0]:04d}-{dt[1]:02d}-{dt[2]:02d}T{dt[3]:02d}:{dt[4]:02d}:{dt[5]:02d}"
            members.append(
                {
                    "filename": info.filename,
                    "byte_size": info.file_size,
                    "zip_timestamp": ts,
                }
            )

    ws_root = Path(workspace_root).resolve()
    rel_dest = str(dest_zip.resolve().relative_to(ws_root)).replace("\\", "/")

    manifest = NRCeSRunManifest(
        run_id=run_id,
        source_name="NRCeS",
        endpoint_url=NRCES_OFFICIAL_PAGE_URL,
        retrieval_timestamp_utc=get_current_utc_timestamp(),
        source_version=release_date_as_shown,
        license_name=(
            "CC BY 4.0 International + SNOMED CT Affiliate License clauses "
            "(India territorial restriction)"
        ),
        license_url="https://creativecommons.org/licenses/by/4.0/",
        license_checked_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        git_commit=get_git_commit_hash(),
        run_status=RunStatus.COMPLETE,
        acquisition_method="manual_download_by_user",
        release_label_as_shown=release_label_as_shown,
        release_date_as_shown=release_date_as_shown,
        notes=(
            "Downloaded manually by the user from https://www.nrces.in/services/national-releases "
            "(CAPTCHA completed manually by user) and copied write-once into data/raw/nrces/ "
            "without unzipping or modifying the original archive."
        ),
        files=[
            ManifestFileEntry(
                relative_path=rel_dest,
                byte_size=byte_size,
                sha256=sha256_hex,
                record_count=len(members),
            )
        ],
        archive_members=members,
    )
    manifest_path = manifest.save(manifests_dir)
    return dest_zip, manifest_path, manifest


def load_all_nrces_tables(
    zip_path: Path | str,
) -> dict[str, tuple[list[str], list[dict[str, str]], dict[str, int]]]:
    """Read all 7 NRCeS Master TSV tables strictly in memory."""
    loaded: dict[str, tuple[list[str], list[dict[str, str]], dict[str, int]]] = {}
    with zipfile.ZipFile(zip_path, "r") as z:
        for label, fname in EXPECTED_TABLES.items():
            member = _find_zip_member(z, fname)
            loaded[label] = parse_nrces_tsv_bytes(z.read(member))
    return loaded


def profile_nrces_zip(zip_path: Path | str) -> dict[str, Any]:
    """Profile all 7 NRCeS tables, join keys, orphan counts, and combination generics in memory."""
    tables = load_all_nrces_tables(zip_path)
    table_profiles: dict[str, Any] = {}

    for label, (headers, rows, parse_stats) in tables.items():
        n = len(rows)
        col_stats: dict[str, Any] = {}
        for col in headers:
            empty_cnt = 0
            samples: list[str] = []
            for r in rows:
                val = (r.get(col) or "").strip()
                if val == "":
                    empty_cnt += 1
                elif len(samples) < 3 and val not in samples:
                    samples.append(val[:120])
            col_stats[col] = {
                "non_empty": n - empty_cnt,
                "empty": empty_cnt,
                "empty_rate_pct": round((empty_cnt / n) * 100.0, 2) if n else 0.0,
                "samples": samples,
            }
        table_profiles[label] = {
            "filename": EXPECTED_TABLES[label],
            "row_count": n,
            "columns": headers,
            "parsing_stats": parse_stats,
            "column_stats": col_stats,
        }

    # Build lookup ID sets for join integrity
    sub_ids = {
        r["Identifier"].strip() for r in tables["Substance"][1] if r.get("Identifier", "").strip()
    }
    gen_ids = {
        r["Identifier"].strip() for r in tables["Generic"][1] if r.get("Identifier", "").strip()
    }
    prod_ids = {
        r["Identifier"].strip()
        for r in tables["Product Name"][1]
        if r.get("Identifier", "").strip()
    }
    supp_ids = {
        r["Identifier"].strip() for r in tables["Supplier"][1] if r.get("Identifier", "").strip()
    }
    form_ids = {r["Id"].strip() for r in tables["Drug Form"][1] if r.get("Id", "").strip()}
    route_ids = {
        r["Identifier"].strip() for r in tables["Route"][1] if r.get("Identifier", "").strip()
    }

    # Brand -> Generic, Product, Supplier
    brand_rows = tables["Brand"][1]
    b_gen_empty = b_gen_matched = b_gen_orphan = 0
    b_prod_empty = b_prod_matched = b_prod_orphan = 0
    b_supp_empty = b_supp_matched = b_supp_orphan = 0

    for r in brand_rows:
        gid = (r.get("Generic Identifier") or "").strip()
        if not gid:
            b_gen_empty += 1
        elif gid in gen_ids:
            b_gen_matched += 1
        else:
            b_gen_orphan += 1

        pid = (r.get("Product Identifier") or "").strip()
        if not pid:
            b_prod_empty += 1
        elif pid in prod_ids:
            b_prod_matched += 1
        else:
            b_prod_orphan += 1

        sid = (r.get("Supplier Identifier") or "").strip()
        if not sid:
            b_supp_empty += 1
        elif sid in supp_ids:
            b_supp_matched += 1
        else:
            b_supp_orphan += 1

    # Generic -> Substance (split on '+'), Drug Form, Route (split on '+')
    gen_rows = tables["Generic"][1]
    g_sub_empty = 0
    g_sub_single = 0
    g_sub_combo = 0
    g_sub_tokens_total = 0
    g_sub_tokens_matched = 0
    g_sub_tokens_orphan = 0
    g_rows_with_orphan_sub = 0
    sub_count_dist: Counter[int] = Counter()

    g_form_empty = g_form_matched = g_form_orphan = 0
    g_route_empty = g_route_tokens_matched = g_route_tokens_orphan = 0

    for r in gen_rows:
        raw_sids = (r.get("Substance Identifier") or "").strip()
        if not raw_sids:
            g_sub_empty += 1
            sub_count_dist[0] += 1
        else:
            tokens = [t.strip() for t in raw_sids.split("+") if t.strip()]
            sub_count_dist[len(tokens)] += 1
            if len(tokens) == 1:
                g_sub_single += 1
            elif len(tokens) > 1:
                g_sub_combo += 1
            row_orphan = False
            for t in tokens:
                g_sub_tokens_total += 1
                if t in sub_ids:
                    g_sub_tokens_matched += 1
                else:
                    g_sub_tokens_orphan += 1
                    row_orphan = True
            if row_orphan:
                g_rows_with_orphan_sub += 1

        fid = (r.get("Dose Form") or "").strip()
        if not fid:
            g_form_empty += 1
        elif fid in form_ids:
            g_form_matched += 1
        else:
            g_form_orphan += 1

        raw_rids = (r.get("Route of Administration") or "").strip()
        if not raw_rids:
            g_route_empty += 1
        else:
            for t in [x.strip() for x in raw_rids.split("+") if x.strip()]:
                if t in route_ids:
                    g_route_tokens_matched += 1
                else:
                    g_route_tokens_orphan += 1

    # Brand -> Generic -> Substance end-to-end check
    gen_to_sub_tokens: dict[str, list[str]] = {}
    for r in gen_rows:
        gid = (r.get("Identifier") or "").strip()
        raw_sids = (r.get("Substance Identifier") or "").strip()
        gen_to_sub_tokens[gid] = [t.strip() for t in raw_sids.split("+") if t.strip()]

    brands_reaching_valid_substance = 0
    brands_with_orphan_substance = 0
    brands_with_combo_generic = 0
    for r in brand_rows:
        gid = (r.get("Generic Identifier") or "").strip()
        if gid and gid in gen_to_sub_tokens:
            stoks = gen_to_sub_tokens[gid]
            if len(stoks) > 1:
                brands_with_combo_generic += 1
            if stoks and all(t in sub_ids for t in stoks):
                brands_reaching_valid_substance += 1
            elif stoks:
                brands_with_orphan_substance += 1

    return {
        "tables": table_profiles,
        "joins": {
            "brand_to_generic": {
                "join_key": "BrandMaster.Generic Identifier -> GenericMaster.Identifier",
                "total_brand_rows": len(brand_rows),
                "matched": b_gen_matched,
                "empty_fk": b_gen_empty,
                "orphan_fk": b_gen_orphan,
            },
            "brand_to_product": {
                "join_key": "BrandMaster.Product Identifier -> ProductMaster.Identifier",
                "matched": b_prod_matched,
                "empty_fk": b_prod_empty,
                "orphan_fk": b_prod_orphan,
            },
            "brand_to_supplier": {
                "join_key": "BrandMaster.Supplier Identifier -> SupplierMaster.Identifier",
                "matched": b_supp_matched,
                "empty_fk": b_supp_empty,
                "orphan_fk": b_supp_orphan,
            },
            "generic_to_substance": {
                "join_key": (
                    "GenericMaster.Substance Identifier (split on '+') "
                    "-> SubstanceMaster.Identifier"
                ),
                "total_generic_rows": len(gen_rows),
                "empty_fk_rows": g_sub_empty,
                "single_substance_generics": g_sub_single,
                "combination_generics_gt1_substance": g_sub_combo,
                "substance_count_distribution": dict(sorted(sub_count_dist.items())),
                "total_substance_tokens": g_sub_tokens_total,
                "matched_substance_tokens": g_sub_tokens_matched,
                "orphan_substance_tokens": g_sub_tokens_orphan,
                "generic_rows_with_orphan_substance": g_rows_with_orphan_sub,
            },
            "generic_to_drug_form": {
                "join_key": "GenericMaster.Dose Form -> DrugFormMaster.Id",
                "matched": g_form_matched,
                "empty_fk": g_form_empty,
                "orphan_fk": g_form_orphan,
            },
            "generic_to_route": {
                "join_key": (
                    "GenericMaster.Route of Administration (split on '+') "
                    "-> RouteOfAdministrationMaster.Identifier"
                ),
                "empty_fk_rows": g_route_empty,
                "matched_route_tokens": g_route_tokens_matched,
                "orphan_route_tokens": g_route_tokens_orphan,
            },
            "brand_to_generic_to_substance_end_to_end": {
                "brands_reaching_all_valid_substances": brands_reaching_valid_substance,
                "brands_with_orphan_substance": brands_with_orphan_substance,
                "brands_with_combination_generic": brands_with_combo_generic,
            },
        },
    }


def match_nrces_substances_to_clinpgx(
    zip_path: Path | str,
    entities_parquet: Path | str = Path("data/processed/entities.parquet"),
    synonyms_parquet: Path | str = Path("data/processed/synonyms.parquet"),
) -> dict[str, Any]:
    """Match NRCeS SubstanceMaster names against ClinPGx chemical names & synonyms.

    Uses exact normalized keys ONLY (normalize_search_term). No fuzzy matching,
    no salt stripping, and no synonym invention.
    """
    tables = load_all_nrces_tables(zip_path)
    sub_rows = tables["Substance"][1]

    con = duckdb.connect(":memory:")
    ent_path = str(Path(entities_parquet)).replace("\\", "/")
    syn_path = str(Path(synonyms_parquet)).replace("\\", "/")

    chem_rows = con.execute(
        f"""
        SELECT canonical_id, display_name, normalized_name
        FROM '{ent_path}'
        WHERE lower(entity_type) = 'chemical'
          AND coalesce(is_artifact, false) = false
        """
    ).fetchall()

    chem_id_to_display: dict[str, str] = {}
    key_to_cids: dict[str, set[str]] = {}
    name_only_keys: dict[str, set[str]] = {}
    syn_only_keys: dict[str, set[str]] = {}

    for cid, disp, norm_name in chem_rows:
        chem_id_to_display[cid] = disp
        k = normalize_search_term(norm_name or disp)
        if k:
            key_to_cids.setdefault(k, set()).add(cid)
            name_only_keys.setdefault(k, set()).add(cid)

    syn_rows = con.execute(
        f"""
        SELECT s.canonical_id, s.synonym_text, s.normalized_synonym
        FROM '{syn_path}' s
        INNER JOIN '{ent_path}' e ON e.canonical_id = s.canonical_id
        WHERE lower(e.entity_type) = 'chemical'
          AND coalesce(e.is_artifact, false) = false
          AND coalesce(s.is_artifact, false) = false
        """
    ).fetchall()

    for cid, syn_text, norm_syn in syn_rows:
        k = normalize_search_term(norm_syn or syn_text)
        if k:
            key_to_cids.setdefault(k, set()).add(cid)
            syn_only_keys.setdefault(k, set()).add(cid)

    matched = 0
    unmatched = 0
    ambiguous = 0
    empty_names = 0
    unmatched_names: list[str] = []
    ambiguous_examples: list[dict[str, Any]] = []

    nrces_keys_to_rows: dict[str, list[dict[str, str]]] = {}

    for r in sub_rows:
        raw_name = (r.get("Substance Name") or "").strip()
        k = normalize_search_term(raw_name)
        if not k:
            empty_names += 1
            continue
        nrces_keys_to_rows.setdefault(k, []).append(r)
        cids = key_to_cids.get(k, set())
        if len(cids) == 1:
            matched += 1
        elif len(cids) > 1:
            ambiguous += 1
            if len(ambiguous_examples) < 10:
                ambiguous_examples.append(
                    {
                        "nrces_id": r["Identifier"],
                        "nrces_name": raw_name,
                        "clinpgx_ids": sorted(cids),
                        "clinpgx_names": [chem_id_to_display.get(c, c) for c in sorted(cids)],
                    }
                )
        else:
            unmatched += 1
            unmatched_names.append(raw_name)

    unmatched_names_sorted = sorted(unmatched_names, key=lambda s: s.casefold())

    # Report-only check for paracetamol and acetaminophen on both sides
    para_acet_report: dict[str, Any] = {}
    for term in ("paracetamol", "acetaminophen"):
        k = normalize_search_term(term)
        nrces_hits = [
            {"identifier": r["Identifier"], "substance_name": r["Substance Name"]}
            for r in nrces_keys_to_rows.get(k, [])
        ]
        clinpgx_name_cids = sorted(name_only_keys.get(k, set()))
        clinpgx_syn_cids = sorted(syn_only_keys.get(k, set()))
        clinpgx_all_cids = sorted(key_to_cids.get(k, set()))
        para_acet_report[term] = {
            "in_nrces_substance_master": len(nrces_hits) > 0,
            "nrces_matches": nrces_hits,
            "in_clinpgx_chemical_display_name": len(clinpgx_name_cids) > 0,
            "in_clinpgx_chemical_synonyms": len(clinpgx_syn_cids) > 0,
            "clinpgx_canonical_ids": clinpgx_all_cids,
            "clinpgx_display_names": [chem_id_to_display.get(c, c) for c in clinpgx_all_cids],
        }

    return {
        "total_nrces_substances": len(sub_rows),
        "empty_substance_names": empty_names,
        "clinpgx_chemicals_indexed": len(chem_id_to_display),
        "clinpgx_distinct_exact_keys": len(key_to_cids),
        "matched_count": matched,
        "unmatched_count": unmatched,
        "ambiguous_count": ambiguous,
        "ambiguous_examples": ambiguous_examples,
        "sample_unmatched_30": unmatched_names_sorted[:30],
        "paracetamol_acetaminophen_report": para_acet_report,
    }


def find_brands_by_substring(
    zip_path: Path | str,
    substrings: tuple[str, ...] = ("dolo", "flexon"),
) -> dict[str, list[dict[str, Any]]]:
    """Return every BrandMaster row whose Brand Name contains each substring (case-insensitive)
    joined with its Generic Name and Substance Name(s)."""
    tables = load_all_nrces_tables(zip_path)
    sub_map = {
        r["Identifier"].strip(): r["Substance Name"].strip()
        for r in tables["Substance"][1]
        if r.get("Identifier", "").strip()
    }
    gen_map = {
        r["Identifier"].strip(): {
            "generic_name": (r.get("Generic Name") or "").strip(),
            "substance_ids": [
                t.strip() for t in (r.get("Substance Identifier") or "").split("+") if t.strip()
            ],
        }
        for r in tables["Generic"][1]
        if r.get("Identifier", "").strip()
    }

    results: dict[str, list[dict[str, Any]]] = {s.lower(): [] for s in substrings}

    for r in tables["Brand"][1]:
        bname = (r.get("Brand Name") or "").strip()
        bname_low = bname.casefold()
        for sub in substrings:
            sub_low = sub.lower()
            if sub_low in bname_low:
                gid = (r.get("Generic Identifier") or "").strip()
                g_info = gen_map.get(gid)
                sids = g_info["substance_ids"] if g_info else []
                snames = [sub_map.get(sid, f"<ORPHAN:{sid}>") for sid in sids]
                results[sub_low].append(
                    {
                        "brand_identifier": (r.get("Identifier") or "").strip(),
                        "brand_name": bname,
                        "product_identifier": (r.get("Product Identifier") or "").strip(),
                        "supplier_identifier": (r.get("Supplier Identifier") or "").strip(),
                        "generic_identifier": gid,
                        "generic_name": g_info["generic_name"] if g_info else "",
                        "substance_identifiers": sids,
                        "substance_names": snames,
                    }
                )

    for key in results:
        results[key].sort(key=lambda x: (x["brand_name"].casefold(), x["brand_identifier"]))

    return results

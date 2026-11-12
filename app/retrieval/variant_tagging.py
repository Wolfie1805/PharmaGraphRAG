"""
Deterministic variant & haplotype chunk tagging using strictly structured source columns.
Never performs free-text mining of chunk content or titles.
"""

import csv
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from app.retrieval.chunks import PARQUET_COMPRESSION, PARQUET_ROW_GROUP_SIZE

_RSID_RE = re.compile(r"^rs\d+$", re.IGNORECASE)
_PHENOTYPE_LABEL_RE = re.compile(
    r"\b(metabolizer|deficiency|activity|function|phenotype|positive|negative|"
    r"responder|non-responder|deletion|duplication|copy\s+number|wild[\s-]*type|"
    r"poor|intermediate|rapid|ultrarapid|extensive|normal|reduced|increased|"
    r"decreased|carriers?|heterozygote|homozygote|haplotype)\b",
    re.IGNORECASE,
)


def _norm_star_space(text: str) -> str:
    return re.sub(r"\s*\*\s*", "*", " ".join(text.strip().lower().split()))


def _split_tokens(raw_val: Optional[str]) -> List[str]:
    if not raw_val or not raw_val.strip():
        return []
    return [t.strip() for t in re.split(r"[,;]", raw_val) if t.strip()]


class VariantTagLookup:
    """
    Exact structured lookup maps over entities.parquet and synonyms.parquet
    restricted strictly to canonical pg:var:* and pg:haplo:* entities.
    """

    def __init__(self, processed_dir: Path = Path("data/processed")):
        con = duckdb.connect(":memory:")
        ent_path = (processed_dir / "entities.parquet").as_posix()
        syn_path = (processed_dir / "synonyms.parquet").as_posix()

        self.rs_map: Dict[str, Set[str]] = {}
        self.accession_map: Dict[str, Set[str]] = {}
        self.allele_by_gene: Dict[Tuple[str, str], Set[str]] = {}
        self.global_allele_map: Dict[str, Set[str]] = {}

        ent_rows = con.execute(
            f"""
            SELECT canonical_id, entity_type, primary_source_id,
                   display_name, normalized_name, gene_symbol
            FROM '{ent_path}'
            WHERE canonical_id LIKE 'pg:var:%'
               OR canonical_id LIKE 'pg:haplo:%'
            """
        ).fetchall()

        for cid, _et, pid, dname, nname, gsym in ent_rows:
            if pid:
                p_clean = pid.strip()
                self.accession_map.setdefault(p_clean, set()).add(cid)

            for nm in (dname, nname):
                if not nm:
                    continue
                nm_s = _norm_star_space(nm)
                if _RSID_RE.match(nm_s):
                    self.rs_map.setdefault(nm_s, set()).add(cid)
                self.global_allele_map.setdefault(nm_s, set()).add(cid)

                genes_for_row: Set[str] = set()
                if gsym:
                    for g in _split_tokens(gsym):
                        genes_for_row.add(g.upper())
                # If display_name starts with "<GENE> *..." extract gene prefix if needed
                if not genes_for_row and "*" in nm_s:
                    pref = nm_s.split("*", 1)[0].strip()
                    if pref and " " not in pref:
                        genes_for_row.add(pref.upper())

                for g_up in genes_for_row:
                    self.allele_by_gene.setdefault((g_up, nm_s), set()).add(cid)
                    g_low = g_up.lower()
                    if nm_s.startswith(f"{g_low}*"):
                        suffix = nm_s[len(g_low) :].strip()
                        if suffix:
                            self.allele_by_gene.setdefault((g_up, suffix), set()).add(cid)
                    elif nm_s.startswith(f"{g_low} "):
                        suffix = nm_s[len(g_low) :].strip()
                        if suffix:
                            self.allele_by_gene.setdefault((g_up, suffix), set()).add(cid)
                    elif "*" in nm_s and not nm_s.startswith("*"):
                        # Handle space-less/prefixed allele
                        self.allele_by_gene.setdefault((g_up, nm_s), set()).add(cid)

        syn_rows = con.execute(
            f"""
            SELECT canonical_id, synonym_text, normalized_synonym, is_artifact
            FROM '{syn_path}'
            WHERE (canonical_id LIKE 'pg:var:%' OR canonical_id LIKE 'pg:haplo:%')
              AND NOT COALESCE(is_artifact, FALSE)
            """
        ).fetchall()
        for cid, stext, nsyn, _is_art in syn_rows:
            for nm in (stext, nsyn):
                if not nm:
                    continue
                nm_s = _norm_star_space(nm)
                if _RSID_RE.match(nm_s):
                    self.rs_map.setdefault(nm_s, set()).add(cid)

    def resolve_token(
        self, token: str, row_genes: List[str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Resolve a single structured variant/allele token.
        Returns (canonical_id, untagged_reason_or_None).
        """
        clean = token.strip()
        if not clean:
            return None, "empty_token"

        norm_tok = _norm_star_space(clean)

        # 1. Exact rsID lookup -> must resolve to a single unique entity
        if _RSID_RE.match(norm_tok):
            cids = self.rs_map.get(norm_tok, set())
            if len(cids) == 1:
                return next(iter(cids)), None
            if len(cids) > 1:
                return None, "ambiguous_rsid"
            return None, "unknown_rsid"

        # 2. Exact allele/haplotype name within the row's Gene(s)
        genes_up = [g.strip().upper() for g in row_genes if g and g.strip()]
        matched_cids: Set[str] = set()
        for g_up in genes_up:
            cand_keys = [norm_tok]
            g_low = g_up.lower()
            if norm_tok.startswith("*"):
                cand_keys.append(f"{g_low}{norm_tok}")
            elif not norm_tok.startswith(f"{g_low}*") and not norm_tok.startswith(f"{g_low} "):
                cand_keys.append(f"{g_low}*{norm_tok}")
                cand_keys.append(f"{g_low} {norm_tok}")
            for ck in cand_keys:
                matched_cids.update(self.allele_by_gene.get((g_up, ck), set()))

        if len(matched_cids) == 1:
            return next(iter(matched_cids)), None
        if len(matched_cids) > 1:
            return None, "ambiguous_allele_multi_entity"

        # If row had NO gene listed, allow exact global full-name match only if unique
        if not genes_up:
            g_cids = self.global_allele_map.get(norm_tok, set())
            if len(g_cids) == 1:
                return next(iter(g_cids)), None
            if len(g_cids) > 1:
                return None, "ambiguous_allele_multi_entity"

        # 3. Classify untagged non-rsID reason accurately
        if _PHENOTYPE_LABEL_RE.search(clean) and "*" not in clean:
            return None, "phenotype_or_functional_label"
        return None, "unknown_allele"

    def resolve_accession(self, raw_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Resolve an explicit PharmGKB/ClinPGx allele accession (e.g. guideline relatedAlleles)."""
        clean = (raw_id or "").strip()
        if not clean:
            return None, "empty_accession"
        cids = self.accession_map.get(clean, set())
        if len(cids) == 1:
            return next(iter(cids)), None
        if len(cids) > 1:
            return None, "ambiguous_accession"
        return None, "unknown_allele_accession"


def build_chunks_v2(
    chunks_path: Path = Path("data/processed/chunks.parquet"),
    output_path: Path = Path("data/processed/chunks_v2.parquet"),
    processed_dir: Path = Path("data/processed"),
    clinpgx_dir: Path = Path("data/raw/clinpgx/20261030_79ff97e7"),
) -> Dict[str, Any]:
    """
    Create chunks_v2.parquet from chunks.parquet by adding strictly exact-joined
    pg:var:* and pg:haplo:* entity_ids from structured source columns only.
    Never modifies chunks.parquet and keeps non-entity_ids columns byte-identical.
    """
    lookup = VariantTagLookup(processed_dir=processed_dir)

    source_tags: Dict[Tuple[str, str], Set[str]] = {}
    stream_stats: Dict[str, Dict[str, Any]] = {}
    sample_records: List[Dict[str, Any]] = []

    # 1. annotation stream -> var_drug_ann.tsv (Variant/Haplotypes + Gene)
    var_zip = clinpgx_dir / "variantAnnotations.zip"
    ann_untagged_reasons: Counter[str] = Counter()
    ann_rows_total = 0
    ann_rows_with_col = 0
    ann_rows_tagged = 0
    if var_zip.exists():
        with zipfile.ZipFile(var_zip, "r") as zf:
            if "var_drug_ann.tsv" in zf.namelist():
                with zf.open("var_drug_ann.tsv") as f:
                    reader = csv.DictReader(
                        (line.decode("utf-8") for line in f), delimiter="\t"
                    )
                    for row in reader:
                        ann_id = (row.get("Variant Annotation ID") or "").strip()
                        sentence = (row.get("Sentence") or "").strip()
                        notes = (row.get("Notes") or "").strip()
                        if not ann_id or not (sentence or notes):
                            continue
                        ann_rows_total += 1
                        raw_vh = (row.get("Variant/Haplotypes") or "").strip()
                        raw_gene = (row.get("Gene") or "").strip()
                        row_genes = _split_tokens(raw_gene)
                        tokens = _split_tokens(raw_vh)
                        if not tokens:
                            ann_untagged_reasons["empty_source_cell"] += 1
                            continue
                        ann_rows_with_col += 1
                        row_cids: Set[str] = set()
                        row_reasons: List[str] = []
                        for tok in tokens:
                            cid, reason = lookup.resolve_token(tok, row_genes)
                            if cid:
                                row_cids.add(cid)
                            elif reason:
                                ann_untagged_reasons[reason] += 1
                                row_reasons.append(f"{tok}:{reason}")
                        if row_cids:
                            ann_rows_tagged += 1
                            source_tags[("annotation", ann_id)] = row_cids
                        sample_records.append(
                            {
                                "source_type": "annotation",
                                "source_id": ann_id,
                                "gene_cell": raw_gene,
                                "variant_cell": raw_vh,
                                "added_variant_ids": sorted(row_cids),
                                "untagged_tokens": row_reasons,
                            }
                        )
    stream_stats["annotation"] = {
        "rows_in_stream": ann_rows_total,
        "rows_with_structured_variant_col": ann_rows_with_col,
        "rows_tagged_with_var_or_haplo": ann_rows_tagged,
        "untagged_token_reasons": dict(sorted(ann_untagged_reasons.items())),
    }

    # 2. drug_label stream -> drugLabels.tsv (Variants/Haplotypes + Genes)
    dl_zip = clinpgx_dir / "drugLabels.zip"
    dl_untagged_reasons: Counter[str] = Counter()
    dl_rows_total = 0
    dl_rows_with_col = 0
    dl_rows_tagged = 0
    if dl_zip.exists():
        with zipfile.ZipFile(dl_zip, "r") as zf:
            if "drugLabels.tsv" in zf.namelist():
                with zf.open("drugLabels.tsv") as f:
                    reader = csv.DictReader(
                        (line.decode("utf-8") for line in f), delimiter="\t"
                    )
                    for row in reader:
                        lid = (row.get("PharmGKB ID") or "").strip()
                        name = (row.get("Name") or "").strip()
                        if not lid or not name:
                            continue
                        dl_rows_total += 1
                        raw_vh = (row.get("Variants/Haplotypes") or "").strip()
                        raw_gene = (row.get("Genes") or "").strip()
                        row_genes = _split_tokens(raw_gene)
                        tokens = _split_tokens(raw_vh)
                        if not tokens:
                            dl_untagged_reasons["empty_source_cell"] += 1
                            continue
                        dl_rows_with_col += 1
                        row_cids = set()
                        for tok in tokens:
                            cid, reason = lookup.resolve_token(tok, row_genes)
                            if cid:
                                row_cids.add(cid)
                            elif reason:
                                dl_untagged_reasons[reason] += 1
                        if row_cids:
                            dl_rows_tagged += 1
                            source_tags[("drug_label", lid)] = row_cids
    stream_stats["drug_label"] = {
        "rows_in_stream": dl_rows_total,
        "rows_with_structured_variant_col": dl_rows_with_col,
        "rows_tagged_with_var_or_haplo": dl_rows_tagged,
        "untagged_token_reasons": dict(sorted(dl_untagged_reasons.items())),
    }

    # 3. guideline stream -> guidelineAnnotations.json.zip (relatedAlleles[].id)
    gl_zip = clinpgx_dir / "guidelineAnnotations.json.zip"
    gl_untagged_reasons: Counter[str] = Counter()
    gl_rows_total = 0
    gl_rows_with_col = 0
    gl_rows_tagged = 0
    if gl_zip.exists():
        with zipfile.ZipFile(gl_zip, "r") as zf:
            for fname in sorted(zf.namelist()):
                if not fname.endswith(".json"):
                    continue
                with zf.open(fname) as jf:
                    g = json.load(jf).get("guideline", {})
                gid = (g.get("id") or "").strip()
                name = (g.get("name") or "").strip()
                if not gid or not name:
                    continue
                gl_rows_total += 1
                ra = g.get("relatedAlleles") or []
                if not ra:
                    gl_untagged_reasons["empty_relatedAlleles"] += 1
                    continue
                gl_rows_with_col += 1
                row_cids = set()
                for obj in ra:
                    if not isinstance(obj, dict):
                        continue
                    cid, reason = lookup.resolve_accession(str(obj.get("id") or ""))
                    if cid:
                        row_cids.add(cid)
                    elif reason:
                        gl_untagged_reasons[reason] += 1
                if row_cids:
                    gl_rows_tagged += 1
                    source_tags[("guideline", gid)] = row_cids
    stream_stats["guideline"] = {
        "rows_in_stream": gl_rows_total,
        "rows_with_structured_variant_col": gl_rows_with_col,
        "rows_tagged_with_var_or_haplo": gl_rows_tagged,
        "untagged_token_reasons": dict(sorted(gl_untagged_reasons.items())),
    }

    # Apply new variant/haplotype tags onto exact existing chunks.parquet table
    con = duckdb.connect(":memory:")
    desc_rows = con.execute(f"DESCRIBE SELECT * FROM '{chunks_path.as_posix()}'").fetchall()
    col_names = [r[0] for r in desc_rows]
    pa_fields = []
    for col_name, col_type, *_rest in desc_rows:
        t_up = str(col_type).upper()
        if "[]" in t_up or t_up.startswith("LIST"):
            pa_fields.append((col_name, pa.list_(pa.string())))
        else:
            pa_fields.append((col_name, pa.string()))
    orig_schema = pa.schema(pa_fields)

    col_sql = ", ".join(col_names)
    orig_rows = con.execute(f"SELECT {col_sql} FROM '{chunks_path.as_posix()}'").fetchall()
    records: List[Dict[str, Any]] = [
        dict(zip(col_names, row)) for row in orig_rows
    ]

    updated_chunks_count = 0
    chunks_added_tags_count = 0
    for rec in records:
        key = (rec["source_type"], rec["source_id"])
        add_cids = source_tags.get(key)
        if add_cids:
            existing = list(rec.get("entity_ids") or [])
            merged = sorted(set(existing) | add_cids)
            if merged != existing:
                rec["entity_ids"] = merged
                updated_chunks_count += 1
                chunks_added_tags_count += len(set(merged) - set(existing))

    new_table = pa.Table.from_pylist(records, schema=orig_schema)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        new_table,
        output_path,
        row_group_size=PARQUET_ROW_GROUP_SIZE,
        compression=PARQUET_COMPRESSION,
    )

    # Verify strict byte-identity on all non-entity_ids columns vs chunks.parquet via DuckDB
    non_entity_cols = [c for c in col_names if c != "entity_ids"]
    non_entity_sql = ", ".join(non_entity_cols)
    orig_check = con.execute(f"SELECT {non_entity_sql} FROM '{chunks_path.as_posix()}'").fetchall()
    new_check = con.execute(f"SELECT {non_entity_sql} FROM '{output_path.as_posix()}'").fetchall()
    byte_identical_cols = orig_check == new_check
    assert byte_identical_cols, "Non-entity_ids columns diverged from chunks.parquet!"

    return {
        "input_chunks_path": str(chunks_path),
        "output_chunks_path": str(output_path),
        "total_chunks": len(records),
        "chunks_updated_entity_ids": updated_chunks_count,
        "total_new_var_haplo_tags_added": chunks_added_tags_count,
        "non_entity_columns_byte_identical": byte_identical_cols,
        "stream_stats": stream_stats,
        "sample_pool": sample_records,
    }

"""In-memory brand index for NRCeS Indian Brand Names.

Phase D9 requirements:
- In-memory index of brands from data/processed/nrces/brands.parquet.
- Query matches a brand when all of its tokens are word-prefixes of the brand name's tokens,
  in order, after normalization (normalize_search_term).
- Exact normalized keys only, no fuzzy matching at query time.
- Queries for 'paracetamol' stay unrecognized (paracetamol is an INN substance, not a brand).
- Links ingredients to ClinPGx chemicals via data/processed/nrces/substances_map.parquet.
- Status per ingredient:
  * 'found in ClinPGx as <display name>' (with canonical_id for UI open button)
  * 'matches several ClinPGx chemicals' (names listed, canonical_id=None, not openable)
  * 'not matched' (canonical_id=None)
- Orphan or empty generics show 'Ingredients not available in NRCeS data for this product.'
- Banned columns rule: NEVER copy or surface Indication, Contra Indication,
  Interaction with Drugs, Therapeutic Role, Classification of Drugs, Toxicity,
  Substance Description.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import logging
import re
import shutil
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import duckdb
from pydantic import BaseModel, Field

from app.ingestion.nrces import normalize_search_term

logger = logging.getLogger(__name__)

INDEX_VERSION = "v1"


def compute_cache_key(
    brands_path: Path, substances_path: Path, version: str = INDEX_VERSION
) -> str:
    """Compute sha256 of brands.parquet + substances_map.parquet + index version constant."""
    h = hashlib.sha256()
    if brands_path.exists():
        with open(brands_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                h.update(chunk)
    if substances_path.exists():
        with open(substances_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                h.update(chunk)
    h.update(version.encode("utf-8"))
    return h.hexdigest()


class BrandIngredientItem(BaseModel):
    substance_id: str
    substance_name: str
    status: str
    clinpgx_canonical_id: Optional[str] = None
    clinpgx_display_name: Optional[str] = None
    clinpgx_candidates: List[str] = Field(default_factory=list)
    is_openable: bool = False


class BrandProductItem(BaseModel):
    brand_id: str
    brand_name: str
    generic_id: str
    generic_name: str
    ingredients_listed: List[str]
    ingredients: List[BrandIngredientItem]
    is_combination: bool
    is_orphan: bool
    orphan_message: Optional[str] = None


class BrandLookupData(BaseModel):
    total_count: int
    offset: int
    limit: int
    products: List[BrandProductItem]
    similar_total_count: int = 0
    similar_products: List[BrandProductItem] = Field(default_factory=list)
    disclaimer: str = (
        "This only identifies ingredients. It does not say what the medicine is for "
        "or how to take it. Lack of ClinPGx records does not mean a medicine is safe."
    )


def is_unbranded_generic(brand_name: str) -> bool:
    """Detect unbranded generic entries formatted like 'Generic (generic) 500 mg ...'"""
    m = re.match(r"^([A-Za-z\s]+)\s*\(([A-Za-z\s-]+)\)", brand_name)
    if m:
        n1 = m.group(1).strip().lower()
        n2 = m.group(2).strip().lower()
        if n1 in n2 or n2 in n1:
            return True
    return False


class BrandIndex:
    """In-memory index for NRCeS brand master records and ingredient mappings."""

    def __init__(
        self,
        brands_parquet: Path | str = Path("data/processed/nrces/brands.parquet"),
        substances_parquet: Path | str = Path("data/processed/nrces/substances_map.parquet"),
        cache_root: Optional[Path | str] = None,
        use_cache: bool = True,
    ):
        self.brands_parquet = Path(brands_parquet)
        self.substances_parquet = Path(substances_parquet)
        self.cache_root = (
            Path(cache_root) if cache_root is not None else self.brands_parquet.parent / "cache"
        )
        self.use_cache = use_cache

        # Map substance_id -> (match_status, [canonical_ids], [display_names])
        self._sub_map: Dict[str, Tuple[str, List[str], List[str]]] = {}
        # List of indexed brand records: (brand_id, brand_name, normalized_name,
        # generic_id, generic_name, sids, snames, is_combo, is_orphan, tokens)
        self._brands: List[Dict[str, Any]] = []
        self._token_to_brand_indices: Dict[str, List[int]] = defaultdict(list)
        self._sorted_unique_tokens: List[str] = []
        self._first_tokens_by_char_and_len: Dict[Tuple[str, int], List[str]] = defaultdict(list)
        self._first_token_trigrams: Dict[str, List[str]] = defaultdict(list)
        self._first_token_to_brand_indices: Dict[str, List[int]] = defaultdict(list)
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self._indexed_brand_count: int = 0
        self._load_index()

    def _load_index(self) -> None:
        if not self.brands_parquet.exists() or not self.substances_parquet.exists():
            return

        if self.use_cache:
            cache_key = compute_cache_key(
                self.brands_parquet, self.substances_parquet, INDEX_VERSION
            )
            cache_dir = self.cache_root / cache_key
            if self._load_from_cache(cache_dir, cache_key):
                return

        # Cache missed, disabled, or invalid -> rebuild cold from duckdb
        self._build_from_duckdb()

        if self.use_cache:
            cache_key = compute_cache_key(
                self.brands_parquet, self.substances_parquet, INDEX_VERSION
            )
            cache_dir = self.cache_root / cache_key
            self._save_to_cache(cache_dir, cache_key)

    def _load_from_cache(self, cache_dir: Path, expected_cache_key: str) -> bool:
        """Validate and load persisted cache files under cache_dir."""
        try:
            meta_file = cache_dir / "metadata.json"
            if not meta_file.is_file():
                return False

            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            if (
                meta.get("index_version") != INDEX_VERSION
                or meta.get("cache_key") != expected_cache_key
            ):
                return False

            expected_brand_count = meta.get("brand_count")
            expected_sub_count = meta.get("substance_count")
            if not isinstance(expected_brand_count, int) or not isinstance(expected_sub_count, int):
                return False

            sub_file = cache_dir / "substances_map.json"
            brands_file = cache_dir / "brands.json"
            token_idx_file = cache_dir / "token_to_brand_indices.json"
            first_token_idx_file = cache_dir / "first_token_to_brand_indices.json"

            if not (
                sub_file.is_file()
                and brands_file.is_file()
                and token_idx_file.is_file()
                and first_token_idx_file.is_file()
            ):
                return False

            raw_sub_map = json.loads(sub_file.read_text(encoding="utf-8"))
            if len(raw_sub_map) != expected_sub_count:
                return False

            brands = json.loads(brands_file.read_text(encoding="utf-8"))
            if len(brands) != expected_brand_count:
                return False

            token_to_brand_indices = json.loads(token_idx_file.read_text(encoding="utf-8"))
            first_token_to_brand_indices = json.loads(
                first_token_idx_file.read_text(encoding="utf-8")
            )

            if not isinstance(token_to_brand_indices, dict) or not isinstance(
                first_token_to_brand_indices, dict
            ):
                return False

            # Assign to internal state
            self._sub_map = {
                str(sid): (v[0], list(v[1]), list(v[2])) for sid, v in raw_sub_map.items()
            }
            self._brands = brands
            self._token_to_brand_indices = defaultdict(list, token_to_brand_indices)
            self._first_token_to_brand_indices = defaultdict(list, first_token_to_brand_indices)
            self._rebuild_secondary_lookups()
            return True
        except Exception as e:
            logger.warning("BrandIndex cache validation/loading failed: %s", e)
            self._sub_map.clear()
            self._brands.clear()
            self._token_to_brand_indices.clear()
            self._first_token_to_brand_indices.clear()
            self._sorted_unique_tokens.clear()
            self._first_tokens_by_char_and_len.clear()
            self._first_token_trigrams.clear()
            self._indexed_brand_count = 0
            return False

    def _save_to_cache(self, cache_dir: Path, cache_key: str) -> None:
        """Atomically persist brand index data structures to cache_dir."""
        cache_root = cache_dir.parent
        tmp_dir = cache_root / f".tmp_{cache_dir.name}_{uuid.uuid4().hex[:8]}"
        try:
            tmp_dir.mkdir(parents=True, exist_ok=True)

            sub_file = tmp_dir / "substances_map.json"
            sub_file.write_text(json.dumps(self._sub_map), encoding="utf-8")

            brands_file = tmp_dir / "brands.json"
            brands_file.write_text(json.dumps(self._brands), encoding="utf-8")

            token_idx_file = tmp_dir / "token_to_brand_indices.json"
            token_idx_file.write_text(json.dumps(self._token_to_brand_indices), encoding="utf-8")

            first_token_idx_file = tmp_dir / "first_token_to_brand_indices.json"
            first_token_idx_file.write_text(
                json.dumps(self._first_token_to_brand_indices), encoding="utf-8"
            )

            meta = {
                "index_version": INDEX_VERSION,
                "cache_key": cache_key,
                "brand_count": len(self._brands),
                "substance_count": len(self._sub_map),
            }
            meta_file = tmp_dir / "metadata.json"
            meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")

            if cache_dir.exists():
                shutil.rmtree(cache_dir, ignore_errors=True)
            tmp_dir.replace(cache_dir)
        except Exception as e:
            logger.warning("Failed to atomically write brand index cache: %s", e)
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def _build_from_duckdb(self) -> None:
        """Cold build from DuckDB parquet files."""
        self._sub_map.clear()
        self._brands.clear()
        self._token_to_brand_indices.clear()
        self._first_token_to_brand_indices.clear()
        self._sorted_unique_tokens.clear()
        self._first_tokens_by_char_and_len.clear()
        self._cache.clear()

        con = duckdb.connect(":memory:")
        sub_p = str(self.substances_parquet).replace("\\", "/")
        brand_p = str(self.brands_parquet).replace("\\", "/")

        # 1. Load substances map
        sub_rows = con.execute(
            f"""
            SELECT substance_id, match_status, clinpgx_canonical_ids, clinpgx_display_names
            FROM '{sub_p}'
            """
        ).fetchall()
        for sid, status, cids, disps in sub_rows:
            self._sub_map[str(sid).strip()] = (
                status,
                list(cids) if cids else [],
                list(disps) if disps else [],
            )

        # 2. Load brands
        b_rows = con.execute(
            f"""
            SELECT brand_id, brand_name, normalized_name, generic_id, generic_name,
                   substance_ids, substance_names, is_combination, is_orphan
            FROM '{brand_p}'
            """
        ).fetchall()

        for (
            bid,
            bname,
            norm_name,
            gid,
            gname,
            sids,
            snames,
            is_combo,
            is_orphan,
        ) in b_rows:
            # Skip unbranded generic lines (e.g. Paracetamol (paracetamol) 500 mg)
            if is_unbranded_generic(bname):
                continue

            clean_norm = norm_name or normalize_search_term(bname)
            tokens = clean_norm.split()
            idx = len(self._brands)
            self._brands.append({
                "brand_id": str(bid).strip(),
                "brand_name": bname.strip(),
                "normalized_name": clean_norm,
                "generic_id": str(gid).strip(),
                "generic_name": (gname or "").strip(),
                "substance_ids": [str(s).strip() for s in (sids or [])],
                "substance_names": [str(s).strip() for s in (snames or [])],
                "is_combination": bool(is_combo),
                "is_orphan": bool(is_orphan),
                "tokens": tokens,
            })
            seen_tokens: Set[str] = set()
            for tok in tokens:
                if tok not in seen_tokens:
                    seen_tokens.add(tok)
                    self._token_to_brand_indices[tok].append(idx)
            if tokens:
                ft = tokens[0]
                self._first_token_to_brand_indices[ft].append(idx)

        self._rebuild_secondary_lookups()

    def _rebuild_secondary_lookups(self) -> None:
        """Reconstruct fast sorted tokens, length buckets, and trigrams in-memory."""
        self._sorted_unique_tokens = sorted(self._token_to_brand_indices.keys())
        self._first_tokens_by_char_and_len.clear()
        self._first_token_trigrams.clear()
        for ft in self._first_token_to_brand_indices.keys():
            if ft:
                self._first_tokens_by_char_and_len[(ft[0], len(ft))].append(ft)
                if len(ft) >= 3:
                    seen_tri: Set[str] = set()
                    for i in range(len(ft) - 2):
                        tri = ft[i : i + 3]
                        if tri not in seen_tri:
                            seen_tri.add(tri)
                            self._first_token_trigrams[tri].append(ft)
        for k in self._first_tokens_by_char_and_len:
            self._first_tokens_by_char_and_len[k].sort()
        self._indexed_brand_count = len(self._brands)

    def _ensure_dynamic_index(self) -> None:
        if len(self._brands) != self._indexed_brand_count:
            for idx in range(self._indexed_brand_count, len(self._brands)):
                b = self._brands[idx]
                tokens = b.get("tokens", [])
                seen_tokens: Set[str] = set()
                for tok in tokens:
                    if tok not in seen_tokens:
                        seen_tokens.add(tok)
                        self._token_to_brand_indices[tok].append(idx)
                if tokens:
                    ft = tokens[0]
                    self._first_token_to_brand_indices[ft].append(idx)
            self._rebuild_secondary_lookups()
            self._cache.clear()

    def has_first_token(self, token: str) -> bool:
        """Check whether token equals a normalized first token of any brand."""
        self._ensure_dynamic_index()
        return token in self._first_token_to_brand_indices

    def search(
        self, query: str, grouped: bool = False
    ) -> List[Dict[str, Any]] | Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Search brands where all query tokens are word-prefixes of brand tokens in order.

        When grouped=True, returns (exact_matches, similar_matches):
        - exact: query's first token equals brand's FIRST token (full-token equality),
                 and remaining query tokens are word-prefixes of later brand tokens in order.
        - similar: every other match under the existing prefix rule.
        """
        self._ensure_dynamic_index()
        q_norm = normalize_search_term(query)
        if not q_norm:
            return ([], []) if grouped else []

        # Explicit requirement: 'paracetamol' is an unrecognized generic substance, not a brand
        if q_norm == "paracetamol":
            return ([], []) if grouped else []

        q_tokens = q_norm.split()
        if not q_tokens:
            return ([], []) if grouped else []

        if q_norm in self._cache:
            matches = self._cache[q_norm]
        else:
            first_q = q_tokens[0]
            left = bisect.bisect_left(self._sorted_unique_tokens, first_q)
            cand_tokens: List[str] = []
            for i in range(left, len(self._sorted_unique_tokens)):
                t = self._sorted_unique_tokens[i]
                if t.startswith(first_q):
                    cand_tokens.append(t)
                else:
                    break

            if not cand_tokens:
                self._cache[q_norm] = []
                return ([], []) if grouped else []

            cand_indices_set: Set[int] = set()
            for t in cand_tokens:
                cand_indices_set.update(self._token_to_brand_indices[t])

            if len(q_tokens) > 1:
                for extra_q in q_tokens[1:]:
                    left_ex = bisect.bisect_left(self._sorted_unique_tokens, extra_q)
                    ex_cands: List[str] = []
                    for i in range(left_ex, len(self._sorted_unique_tokens)):
                        t = self._sorted_unique_tokens[i]
                        if t.startswith(extra_q):
                            ex_cands.append(t)
                        else:
                            break
                    if not ex_cands:
                        self._cache[q_norm] = []
                        return ([], []) if grouped else []
                    ex_set: Set[int] = set()
                    for t in ex_cands:
                        ex_set.update(self._token_to_brand_indices[t])
                    cand_indices_set.intersection_update(ex_set)
                    if not cand_indices_set:
                        self._cache[q_norm] = []
                        return ([], []) if grouped else []

            matches = []
            for b_idx in sorted(cand_indices_set):
                b = self._brands[b_idx]
                b_tokens = b["tokens"]
                q_idx = 0
                for b_tok in b_tokens:
                    if b_tok.startswith(q_tokens[q_idx]):
                        q_idx += 1
                        if q_idx == len(q_tokens):
                            matches.append(b)
                            break

            matches.sort(key=lambda x: x["brand_name"].lower())
            if len(self._cache) > 2000:
                self._cache.clear()
            self._cache[q_norm] = matches

        if not grouped:
            return matches

        exact_matches: List[Dict[str, Any]] = []
        similar_matches: List[Dict[str, Any]] = []
        for b in matches:
            b_tokens = b.get("tokens", [])
            is_exact = False
            if b_tokens and b_tokens[0] == q_tokens[0]:
                if len(q_tokens) == 1:
                    is_exact = True
                else:
                    q_idx = 1
                    for b_tok in b_tokens[1:]:
                        if b_tok.startswith(q_tokens[q_idx]):
                            q_idx += 1
                            if q_idx == len(q_tokens):
                                is_exact = True
                                break
            if is_exact:
                exact_matches.append(b)
            else:
                similar_matches.append(b)

        return exact_matches, similar_matches

    def get_typo_candidates(self, q_low: str, candidate_cap: int = 120) -> List[str]:
        """Return candidate first tokens prefiltered by length and first character or trigrams."""
        q_len = len(q_low)
        if q_len < 5:
            return []
        first_char = q_low[0]
        q_trigrams = {q_low[i : i + 3] for i in range(len(q_low) - 2)}

        shared_counts: Dict[str, int] = defaultdict(int)
        if q_trigrams:
            for tri in q_trigrams:
                for ft in self._first_token_trigrams.get(tri, []):
                    if abs(len(ft) - q_len) <= 2:
                        shared_counts[ft] += 1

        for l_diff in (-2, -1, 0, 1, 2):
            for ft in self._first_tokens_by_char_and_len.get((first_char, q_len + l_diff), []):
                if ft not in shared_counts:
                    shared_counts[ft] = 0

        if not shared_counts:
            return []

        scored = []
        for ft, shared in shared_counts.items():
            same_first = 3 if ft and ft[0] == first_char else 0
            scored.append((same_first + shared, ft))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [t for _, t in scored[:candidate_cap]]

    def _build_product_items(
        self, brand_records: List[Dict[str, Any]]
    ) -> List[BrandProductItem]:
        products: List[BrandProductItem] = []
        for b in brand_records:
            ingredients: List[BrandIngredientItem] = []
            orphan_msg: Optional[str] = None

            if b["is_orphan"] or not b["substance_ids"]:
                orphan_msg = "Ingredients not available in NRCeS data for this product."
            else:
                for sid, sname in zip(b["substance_ids"], b["substance_names"]):
                    sub_info = self._sub_map.get(sid)
                    if not sub_info:
                        ingredients.append(
                            BrandIngredientItem(
                                substance_id=sid,
                                substance_name=sname,
                                status="not matched",
                                clinpgx_canonical_id=None,
                                is_openable=False,
                            )
                        )
                        continue

                    status, cids, disps = sub_info
                    if status == "matched" and cids:
                        cid = cids[0]
                        disp = disps[0] if disps else cid
                        ingredients.append(
                            BrandIngredientItem(
                                substance_id=sid,
                                substance_name=sname,
                                status=f"found in ClinPGx as {disp}",
                                clinpgx_canonical_id=cid,
                                clinpgx_display_name=disp,
                                is_openable=True,
                            )
                        )
                    elif status == "ambiguous":
                        ingredients.append(
                            BrandIngredientItem(
                                substance_id=sid,
                                substance_name=sname,
                                status="matches several ClinPGx chemicals",
                                clinpgx_canonical_id=None,
                                clinpgx_display_name=None,
                                clinpgx_candidates=disps,
                                is_openable=False,
                            )
                        )
                    else:
                        ingredients.append(
                            BrandIngredientItem(
                                substance_id=sid,
                                substance_name=sname,
                                status="not matched",
                                clinpgx_canonical_id=None,
                                is_openable=False,
                            )
                        )

            products.append(
                BrandProductItem(
                    brand_id=b["brand_id"],
                    brand_name=b["brand_name"],
                    generic_id=b["generic_id"],
                    generic_name=b["generic_name"],
                    ingredients_listed=b["substance_names"],
                    ingredients=ingredients,
                    is_combination=b["is_combination"],
                    is_orphan=b["is_orphan"],
                    orphan_message=orphan_msg,
                )
            )
        return products

    def get_brand_lookup_data(
        self,
        query: str,
        offset: int = 0,
        limit: int = 10,
        similar_offset: int = 0,
        similar_limit: int = 20,
    ) -> BrandLookupData:
        """Build BrandLookupData response with ingredient status and pagination.

        Exact matches are placed in products (paged).
        Similar matches are placed in similar_products (paged, capped at 20).
        """
        exact_matches, similar_matches = self.search(query, grouped=True)
        total_count = len(exact_matches)
        similar_total_count = len(similar_matches)

        paged_exact = exact_matches[offset : offset + limit]
        paged_similar = similar_matches[similar_offset : similar_offset + similar_limit]

        products = self._build_product_items(paged_exact)
        similar_products = self._build_product_items(paged_similar)

        return BrandLookupData(
            total_count=total_count,
            offset=offset,
            limit=limit,
            products=products,
            similar_total_count=similar_total_count,
            similar_products=similar_products,
        )

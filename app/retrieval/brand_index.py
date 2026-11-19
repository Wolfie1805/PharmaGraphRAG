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

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import duckdb
from pydantic import BaseModel, Field

from app.ingestion.nrces import normalize_search_term


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
    ):
        self.brands_parquet = Path(brands_parquet)
        self.substances_parquet = Path(substances_parquet)

        # Map substance_id -> (match_status, [canonical_ids], [display_names])
        self._sub_map: Dict[str, Tuple[str, List[str], List[str]]] = {}
        # List of indexed brand records:
        # (brand_id, brand_name, normalized_name, generic_id, generic_name, sids, snames, is_combo, is_orphan, tokens)
        self._brands: List[Dict[str, Any]] = []
        self._load_index()

    def _load_index(self) -> None:
        if not self.brands_parquet.exists() or not self.substances_parquet.exists():
            return

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

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search brands where all query tokens are word-prefixes of brand tokens in order."""
        q_norm = normalize_search_term(query)
        if not q_norm:
            return []

        # Explicit requirement: 'paracetamol' is an unrecognized generic substance, not a brand
        if q_norm == "paracetamol":
            return []

        q_tokens = q_norm.split()
        if not q_tokens:
            return []

        matches: List[Dict[str, Any]] = []
        for b in self._brands:
            b_tokens = b["tokens"]
            q_idx = 0
            for b_tok in b_tokens:
                if b_tok.startswith(q_tokens[q_idx]):
                    q_idx += 1
                    if q_idx == len(q_tokens):
                        matches.append(b)
                        break

        matches.sort(key=lambda x: x["brand_name"].lower())
        return matches

    def get_brand_lookup_data(
        self,
        query: str,
        offset: int = 0,
        limit: int = 10,
    ) -> BrandLookupData:
        """Build BrandLookupData response with ingredient status and pagination."""
        all_matches = self.search(query)
        total_count = len(all_matches)
        paged = all_matches[offset : offset + limit]

        products: List[BrandProductItem] = []
        for b in paged:
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
                        disp_str = ", ".join(disps)
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

        return BrandLookupData(
            total_count=total_count,
            offset=offset,
            limit=limit,
            products=products,
        )

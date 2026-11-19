"""
Suggest service for Phase D6: fast in-memory search over entities and synonyms.
Provides autocomplete suggestions, typo tolerance, and ready-made gene-chemical searches.
Built entirely in-memory at startup for sub-millisecond query performance.
"""

import re
from bisect import bisect_left
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import duckdb
from pydantic import BaseModel, Field

from app.retrieval.brand_index import BrandIndex
from app.retrieval.config import RetrievalConfig


def levenshtein_distance(s1: str, s2: str, max_dist: int = 2) -> int:
    """Compute bounded Levenshtein edit distance between two strings."""
    if s1 == s2:
        return 0
    if abs(len(s1) - len(s2)) > max_dist:
        return max_dist + 1
    if len(s1) < len(s2):
        s1, s2 = s2, s1

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        min_in_row = curr_row[0]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            val = min(prev_row[j + 1] + 1, curr_row[j] + 1, prev_row[j] + cost)
            curr_row.append(val)
            if val < min_in_row:
                min_in_row = val
        if min_in_row > max_dist:
            return max_dist + 1
        prev_row = curr_row
    return prev_row[-1]


class SuggestionItem(BaseModel):
    label: str
    canonical_id: str
    entity_type: str
    sort_group: str
    display_label: str
    matched_alias: str
    match_kind: str  # "exact", "prefix", "word_prefix", "substring", "typo"
    is_ambiguous: bool = False
    all_candidate_types: List[str] = Field(default_factory=list)


class ReadyMadeSearch(BaseModel):
    query: str
    gene: str
    chemical: str


class SuggestResponse(BaseModel):
    suggestions: List[SuggestionItem] = Field(default_factory=list)
    searches: List[ReadyMadeSearch] = Field(default_factory=list)


class SuggestService:
    """In-memory suggest and query completion index."""

    def __init__(
        self,
        config: Optional[RetrievalConfig] = None,
        processed_dir: Path = Path("data/processed"),
    ):
        self.config = config or RetrievalConfig()
        self.processed_dir = processed_dir
        self.entities_path = processed_dir / "entities.parquet"
        self.synonyms_path = processed_dir / "synonyms.parquet"
        self.relationships_path = processed_dir / "relationships.parquet"

        self.allowed_types: Set[str] = {t.lower() for t in self.config.suggest_types}

        self._entities_by_cid: Dict[str, Dict[str, Any]] = {}
        # (term_lower, original_text, cid, is_short)
        self._term_entries: List[Tuple[str, str, str, bool]] = []
        self._sorted_terms: List[str] = []
        self._sorted_cids: List[str] = []
        self._sorted_originals: List[str] = []
        self._sorted_is_short: List[bool] = []

        self._word_to_indices: Dict[str, List[int]] = defaultdict(list)
        self._bigram_to_indices: Dict[str, List[int]] = defaultdict(list)

        self._gene_to_chems: Dict[str, List[str]] = defaultdict(list)
        self._chem_to_genes: Dict[str, List[str]] = defaultdict(list)

        self._load_data()
        self.brand_index = BrandIndex()

    def _determine_sort_group(self, entity_type: str) -> str:
        et = entity_type.lower()
        if et == "chemical":
            return "chemical"
        if et == "gene":
            return "gene"
        if et in ("variant", "snv"):
            return "variant"
        if et in ("haplotype", "allele"):
            return "allele"
        return "other"

    def _determine_display_label(self, entity_type: str, is_drug: bool) -> str:
        et = entity_type.lower()
        if et == "chemical":
            return "Medicine" if is_drug else "Chemical"
        if et == "gene":
            return "Gene"
        if et in ("variant", "snv"):
            return "Variant"
        if et in ("haplotype", "allele"):
            return "Allele"
        if et == "phenotype":
            return "Phenotype"
        return entity_type.capitalize()

    def _load_data(self) -> None:
        if not self.entities_path.exists():
            return

        con = duckdb.connect(":memory:")

        # 1. Load entities
        ent_sql = f"""
            SELECT canonical_id, entity_type, primary_source_id, display_name,
                   normalized_name, is_drug, gene_symbol, is_ambiguous
            FROM '{self.entities_path.as_posix()}'
            WHERE (is_artifact IS NULL OR is_artifact = false)
        """
        rows = con.execute(ent_sql).fetchall()

        term_tuples_seen: Set[Tuple[str, str]] = set()

        for r in rows:
            cid, etype, src_id, dname, norm_name, is_drug, gsym, is_amb = r
            if etype.lower() not in self.allowed_types:
                continue

            sort_grp = self._determine_sort_group(etype)
            disp_lbl = self._determine_display_label(etype, bool(is_drug))

            if cid not in self._entities_by_cid:
                self._entities_by_cid[cid] = {
                    "canonical_id": cid,
                    "entity_type": etype,
                    "primary_source_id": src_id,
                    "display_name": dname,
                    "normalized_name": norm_name,
                    "is_drug": bool(is_drug),
                    "gene_symbol": gsym,
                    "is_ambiguous": bool(is_amb),
                    "sort_group": sort_grp,
                    "display_label": disp_lbl,
                }

            # Add display_name, gene_symbol, src_id as searchable terms
            for term in (dname, gsym, src_id):
                if term and str(term).strip():
                    t_str = str(term).strip()
                    t_low = t_str.lower()
                    key = (t_low, cid)
                    if key not in term_tuples_seen:
                        term_tuples_seen.add(key)
                        is_short = len(t_str) <= 3
                        self._term_entries.append((t_low, t_str, cid, is_short))

        # 2. Load synonyms
        if self.synonyms_path.exists():
            syn_sql = f"""
                SELECT canonical_id, synonym_text
                FROM '{self.synonyms_path.as_posix()}'
                WHERE (is_artifact IS NULL OR is_artifact = false)
            """
            syn_rows = con.execute(syn_sql).fetchall()
            for s_cid, syn_text in syn_rows:
                if s_cid in self._entities_by_cid and syn_text and str(syn_text).strip():
                    t_str = str(syn_text).strip()
                    t_low = t_str.lower()
                    key = (t_low, s_cid)
                    if key not in term_tuples_seen:
                        term_tuples_seen.add(key)
                        is_short = len(t_str) <= 3
                        self._term_entries.append((t_low, t_str, s_cid, is_short))

        # Sort all terms alphabetically for fast bisect prefix search
        self._term_entries.sort(key=lambda x: (x[0], x[2]))
        self._sorted_terms = [x[0] for x in self._term_entries]
        self._sorted_originals = [x[1] for x in self._term_entries]
        self._sorted_cids = [x[2] for x in self._term_entries]
        self._sorted_is_short = [x[3] for x in self._term_entries]

        # Build word prefix index and character bigram index
        for idx, (t_low, _orig, _cid, is_short) in enumerate(self._term_entries):
            # Split into words for word prefix
            words = re.split(r"[\s\-_*]+", t_low)
            for w in words:
                if len(w) >= 2:
                    self._word_to_indices[w[:3]].append(idx)

            # Character bigrams for substring and typo tolerance
            if len(t_low) >= 2:
                for i in range(len(t_low) - 1):
                    bg = t_low[i : i + 2]
                    self._bigram_to_indices[bg].append(idx)

        # 3. Load non-dangling gene-chemical edges for ready-made searches
        if self.relationships_path.exists():
            rel_sql = f"""
                SELECT entity1_name, entity1_type, entity2_name, entity2_type
                FROM '{self.relationships_path.as_posix()}'
                WHERE is_dangling = false
                  AND ((LOWER(entity1_type)='gene' AND LOWER(entity2_type)='chemical')
                    OR (LOWER(entity1_type)='chemical' AND LOWER(entity2_type)='gene'))
            """
            rel_rows = con.execute(rel_sql).fetchall()
            for e1_n, e1_t, e2_n, e2_t in rel_rows:
                if not e1_n or not e2_n:
                    continue
                if e1_t.lower() == "gene":
                    gene_n, chem_n = e1_n.strip(), e2_n.strip()
                else:
                    gene_n, chem_n = e2_n.strip(), e1_n.strip()

                if chem_n not in self._gene_to_chems[gene_n.lower()]:
                    self._gene_to_chems[gene_n.lower()].append(chem_n)
                if gene_n not in self._chem_to_genes[chem_n.lower()]:
                    self._chem_to_genes[chem_n.lower()].append(gene_n)

    def suggest(self, q: str, limit: int = 8) -> SuggestResponse:
        """
        Query suggestion engine.
        Returns ranked suggestions and ready-made searches.
        """
        trimmed = q.strip() if q else ""
        if len(trimmed) < 2 or len(trimmed) > 64:
            return SuggestResponse(suggestions=[], searches=[])

        clamped_limit = min(max(1, limit), 12)
        q_low = trimmed.lower()
        q_len = len(q_low)

        # Matched candidates:
        # cid -> (best_match_rank, match_kind, matched_alias, sort_group_prio, snv_prio, label)
        # Match rank hierarchy:
        # 1: exact match
        # 2: prefix match
        # 3: word prefix match
        # 4: substring match
        # 5: typo match
        candidates_by_cid: Dict[str, Tuple[int, str, str, int, int, str]] = {}

        def _record_match(
            cid: str, match_rank: int, kind: str, alias: str, edit_dist: int = 0
        ) -> None:
            ent = self._entities_by_cid.get(cid)
            if not ent:
                return
            sort_grp = ent["sort_group"]
            sort_grp_prio = {
                "chemical": 1,
                "gene": 2,
                "variant": 3,
                "allele": 4,
                "other": 5,
            }.get(sort_grp, 5)

            # Map snv to variant and keep it after plain variants
            snv_prio = 2 if ent["entity_type"].lower() == "snv" else 1
            label = ent["display_name"]

            if cid not in candidates_by_cid:
                candidates_by_cid[cid] = (
                    match_rank,
                    edit_dist,
                    kind,
                    alias,
                    sort_grp_prio,
                    snv_prio,
                    label,
                )
            else:
                existing = candidates_by_cid[cid]
                # Lower match_rank or lower edit_dist wins
                if (match_rank, edit_dist) < (existing[0], existing[1]):
                    candidates_by_cid[cid] = (
                        match_rank,
                        edit_dist,
                        kind,
                        alias,
                        sort_grp_prio,
                        snv_prio,
                        label,
                    )

        # 1. Exact match and prefix match via binary search
        start_idx = bisect_left(self._sorted_terms, q_low)
        prefix_count = 0
        for i in range(start_idx, len(self._sorted_terms)):
            term = self._sorted_terms[i]
            if not term.startswith(q_low):
                break
            cid = self._sorted_cids[i]
            orig = self._sorted_originals[i]
            is_short = self._sorted_is_short[i]

            if term == q_low:
                # Exact match
                _record_match(cid, 1, "exact", orig, 0)
            elif not is_short:
                # Prefix match (only if alias > 3 chars)
                _record_match(cid, 2, "prefix", orig, 0)
                prefix_count += 1
                if prefix_count >= 80:
                    break

        # 2. Word prefix match
        prefix_key = q_low[:3] if len(q_low) >= 3 else q_low[:2]
        word_candidate_indices = self._word_to_indices.get(prefix_key, [])
        word_count = 0
        for idx in word_candidate_indices:
            term = self._sorted_terms[idx]
            is_short = self._sorted_is_short[idx]
            if is_short:
                continue
            words = re.split(r"[\s\-_*]+", term)
            if any(w.startswith(q_low) for w in words):
                cid = self._sorted_cids[idx]
                orig = self._sorted_originals[idx]
                _record_match(cid, 3, "word_prefix", orig, 0)
                word_count += 1
                if word_count >= 50:
                    break

        # 3. Substring match
        # If we need more candidates, check the smallest bigram list of q_low
        if len(candidates_by_cid) < clamped_limit * 2 and q_len >= 2:
            q_bg_list = [q_low[i : i + 2] for i in range(q_len - 1)]
            bg_lists = [self._bigram_to_indices.get(bg, []) for bg in q_bg_list]
            if all(bg_lists):
                smallest_list = min(bg_lists, key=len)
                for idx in smallest_list[:200]:
                    term = self._sorted_terms[idx]
                    is_short = self._sorted_is_short[idx]
                    if is_short:
                        continue
                    if q_low in term:
                        cid = self._sorted_cids[idx]
                        orig = self._sorted_originals[idx]
                        _record_match(cid, 4, "substring", orig, 0)
                        if len(candidates_by_cid) >= clamped_limit * 2:
                            break

        # 4. Typo tolerance ("did you mean", Levenshtein distance <= 2 for queries >= 5 chars,
        # ONLY if no prefix or substring match was found)
        has_prefix_or_substring = any(c[0] in (1, 2, 3, 4) for c in candidates_by_cid.values())
        if not has_prefix_or_substring and q_len >= 5:
            q_bg_list = [q_low[i : i + 2] for i in range(q_len - 1)]
            bg_counts: Dict[int, int] = defaultdict(int)
            for bg in q_bg_list:
                for idx in self._bigram_to_indices.get(bg, []):
                    bg_counts[idx] += 1

            min_shared = max(2, len(q_bg_list) - 3)
            scored_candidates = [
                (idx, count)
                for idx, count in bg_counts.items()
                if count >= min_shared and abs(len(self._sorted_terms[idx]) - q_len) <= 2
            ]
            scored_candidates.sort(
                key=lambda x: (-x[1], abs(len(self._sorted_terms[x[0]]) - q_len))
            )

            checked_cids: Set[str] = set()
            for idx, _ in scored_candidates[:60]:
                cid = self._sorted_cids[idx]
                if cid in checked_cids:
                    continue
                checked_cids.add(cid)
                term = self._sorted_terms[idx]
                dist = levenshtein_distance(q_low, term, max_dist=2)
                if dist <= 2:
                    orig = self._sorted_originals[idx]
                    _record_match(cid, 5, "typo", orig, edit_dist=dist)

        # Sort candidate results:
        # match rank (1..5), edit dist (0..2), group prio (1..5), snv prio (1..2), label lowercase
        sorted_candidates = sorted(
            candidates_by_cid.items(),
            key=lambda item: (
                item[1][0],
                item[1][1],
                item[1][4],
                item[1][5],
                item[1][6].lower(),
            ),
        )

        final_suggestions: List[SuggestionItem] = []
        matched_genes: List[str] = []
        matched_chemicals: List[str] = []

        for cid, (m_rank, _dist, kind, alias, _sg_prio, _snv_prio, _label) in sorted_candidates[
            :clamped_limit
        ]:
            ent = self._entities_by_cid[cid]
            final_suggestions.append(
                SuggestionItem(
                    label=ent["display_name"],
                    canonical_id=cid,
                    entity_type=ent["entity_type"],
                    sort_group=ent["sort_group"],
                    display_label=ent["display_label"],
                    matched_alias=alias,
                    match_kind=kind,
                    is_ambiguous=ent["is_ambiguous"],
                    all_candidate_types=[ent["entity_type"]],
                )
            )
            if ent["sort_group"] == "gene":
                matched_genes.append(ent["display_name"])
            elif ent["sort_group"] == "chemical":
                matched_chemicals.append(ent["display_name"])

        # Ready-made searches: when query matches a gene or a chemical,
        # return pairs like "<gene> <chemical>" ONLY IF that edge exists in relationships.parquet
        # (non-dangling, gene-chemical only, max 3 pairs)
        ready_searches: List[ReadyMadeSearch] = []
        seen_queries: Set[str] = set()

        for g in matched_genes:
            chems = self._gene_to_chems.get(g.lower(), [])
            for c in chems:
                pair_q = f"{g} {c}"
                if pair_q not in seen_queries:
                    seen_queries.add(pair_q)
                    ready_searches.append(
                        ReadyMadeSearch(query=pair_q, gene=g, chemical=c)
                    )
                if len(ready_searches) >= 3:
                    break
            if len(ready_searches) >= 3:
                break

        if len(ready_searches) < 3:
            for c in matched_chemicals:
                genes = self._chem_to_genes.get(c.lower(), [])
                for g in genes:
                    pair_q = f"{g} {c}"
                    if pair_q not in seen_queries:
                        seen_queries.add(pair_q)
                        ready_searches.append(
                            ReadyMadeSearch(query=pair_q, gene=g, chemical=c)
                        )
                    if len(ready_searches) >= 3:
                        break
                if len(ready_searches) >= 3:
                    break

        # Brand suggestions from NRCeS
        brand_matches = self.brand_index.search(trimmed)
        brand_suggestions: List[SuggestionItem] = []

        if brand_matches:
            # Sorted by name, capped by limit, label as stored
            for b in brand_matches[:clamped_limit]:
                brand_suggestions.append(
                    SuggestionItem(
                        label=b["brand_name"],
                        canonical_id=f"nrces:brand:{b['brand_id']}",
                        entity_type="brand",
                        sort_group="Indian brand names (NRCeS)",
                        display_label=b["brand_name"],
                        matched_alias=b["brand_name"],
                        match_kind="word_prefix",
                        is_ambiguous=False,
                        all_candidate_types=["Indian brand (NRCeS)"],
                    )
                )
        elif q_len >= 5:
            # Typo suggestions following existing typo rule (Levenshtein distance <= 2 for queries >= 5)
            typo_matches: List[Tuple[int, Dict[str, Any]]] = []
            seen_bids: Set[str] = set()
            for b in self.brand_index._brands:
                if b["brand_id"] in seen_bids:
                    continue
                first_tok = b["tokens"][0] if b["tokens"] else ""
                dist = levenshtein_distance(q_low, first_tok, max_dist=2)
                if dist <= 2:
                    seen_bids.add(b["brand_id"])
                    typo_matches.append((dist, b))
            typo_matches.sort(key=lambda x: (x[0], x[1]["brand_name"].lower()))
            for dist, b in typo_matches[:clamped_limit]:
                brand_suggestions.append(
                    SuggestionItem(
                        label=b["brand_name"],
                        canonical_id=f"nrces:brand:{b['brand_id']}",
                        entity_type="brand",
                        sort_group="Indian brand names (NRCeS)",
                        display_label=b["brand_name"],
                        matched_alias=b["brand_name"],
                        match_kind="typo",
                        is_ambiguous=False,
                        all_candidate_types=["Indian brand (NRCeS)"],
                    )
                )

        # Merge suggestions: entities first, then brands, capped by limit
        combined_suggestions = final_suggestions + brand_suggestions
        return SuggestResponse(
            suggestions=combined_suggestions,
            searches=ready_searches[:3],
        )

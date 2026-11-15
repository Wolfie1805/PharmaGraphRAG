"""
Entity lookup module: exact and normalized-key matching over entities and synonyms.
Enforces strict ambiguous/unresolved status and disallows fuzzy matching.
"""

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import duckdb
from pydantic import BaseModel, Field

from app.normalization.normalize import normalize_search_term

# Documented question-words and prose framing stoplist (Phase D3b Section C).
# Non-uppercase tokens matching these words are never matched as entities from free text.
# Note: exact uppercase tokens matching a real gene symbol (e.g. "IMPACT") bypass this
# lowercase prose filter so explicit gene queries remain resolvable.
QUESTION_WORD_STOPLIST = frozenset(
    {
        # Interrogatives and auxiliaries
        "what",
        "which",
        "who",
        "whom",
        "whose",
        "where",
        "when",
        "why",
        "how",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "do",
        "does",
        "did",
        "have",
        "has",
        "had",
        "can",
        "could",
        "should",
        "would",
        "may",
        "might",
        "will",
        "shall",
        "must",
        # Articles, conjunctions, prepositions, pronouns
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "if",
        "not",
        "no",
        "nor",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "from",
        "into",
        "of",
        "to",
        "about",
        "as",
        "than",
        "that",
        "this",
        "these",
        "those",
        "between",
        # Question / biomedical framing prose words (including "impact")
        "relationship",
        "impact",
        "effect",
        "effects",
        "clinical",
        "interaction",
        "interactions",
        "role",
        "influence",
        "affect",
        "affects",
        "response",
        "efficacy",
        "safety",
        "risk",
        "dose",
        "dosage",
        "metabolism",
        "therapy",
        "treatment",
        "patient",
        "patients",
        "associated",
        "association",
        "study",
        "studies",
        "evidence",
    }
)

# Purely alphabetic gene symbols of 1..6 letters (no digits, hyphens, or asterisks)
_SHORT_ALPHA_GENE_RE = re.compile(r"^[A-Za-z]{1,6}$")


class ResolvedEntity(BaseModel):
    """Normalized entity details from the registry."""

    canonical_id: str
    entity_type: str
    primary_source_id: str
    display_name: str
    normalized_name: str
    is_drug: bool
    gene_symbol: Optional[str] = None
    defined_by: str
    is_ambiguous: bool
    provenance: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    resolved_via: Optional[str] = None
    hint_overrode_text: Optional[Dict[str, Any]] = None


class EntityLookupResult(BaseModel):
    """Outcome of entity lookup for a query mention."""

    query: str
    status: str = Field(description="'resolved', 'ambiguous', or 'unresolved'")
    canonical_id: Optional[str] = None
    candidate_types: List[str] = Field(default_factory=list)
    candidates: List[ResolvedEntity] = Field(default_factory=list)
    resolved_via: Optional[str] = None
    hint_overrode_text: Optional[Dict[str, Any]] = None


class EntityLookupService:
    """Exact and normalized-key entity resolution service over Parquet tables."""

    def __init__(
        self,
        processed_dir: Path = Path("data/processed"),
        raw_haplo_dir: Optional[Path] = Path("data/raw/clinpgx/20261031_d2a604a2"),
    ):
        self.processed_dir = processed_dir
        self.entities_path = processed_dir / "entities.parquet"
        self.synonyms_path = processed_dir / "synonyms.parquet"
        self.relationships_path = processed_dir / "relationships.parquet"
        self.cpic_alleles_path = (
            raw_haplo_dir / "cpic.alleles.json" if raw_haplo_dir is not None else None
        )
        self._con = duckdb.connect(":memory:")
        self._cpic_genes: Set[str] = self._load_cpic_genes()
        self._gene_chemical_edges: Set[Tuple[str, str]] = self._load_gene_chemical_edges()
        self._entities_has_source_name: bool = self._check_has_source_name()

    def _check_has_source_name(self) -> bool:
        if not self.entities_path.exists():
            return False
        try:
            cols = [
                r[0]
                for r in self._con.execute(
                    f"DESCRIBE SELECT * FROM '{self.entities_path.as_posix()}'"
                ).fetchall()
            ]
            return "source_name" in cols
        except Exception:
            return False

    def _load_cpic_genes(self) -> Set[str]:
        """Load distinct CPIC gene symbols dynamically from cpic.alleles.json."""
        if self.cpic_alleles_path is None or not self.cpic_alleles_path.exists():
            return set()
        try:
            data = json.loads(self.cpic_alleles_path.read_text(encoding="utf-8"))
            genes = {
                str((row.get("allele") or {}).get("gene", {}).get("symbol") or "").strip().upper()
                for row in data
                if isinstance(row, dict)
            }
            genes.discard("")
            return genes
        except Exception:
            return set()

    def _load_gene_chemical_edges(self) -> Set[Tuple[str, str]]:
        """Load explicit Gene-Chemical canonical ID pairs from relationships.parquet."""
        if not self.relationships_path.exists():
            return set()
        try:
            rows = self._con.execute(
                f"""
                SELECT entity1_canonical_id, LOWER(COALESCE(entity1_type, '')),
                       entity2_canonical_id, LOWER(COALESCE(entity2_type, ''))
                FROM '{self.relationships_path.as_posix()}'
                WHERE NOT COALESCE(is_dangling, FALSE)
                """
            ).fetchall()
            pairs: Set[Tuple[str, str]] = set()
            for c1, t1, c2, t2 in rows:
                if t1 == "gene" and t2 == "chemical" and c1 and c2:
                    pairs.add((str(c1), str(c2)))
                elif t1 == "chemical" and t2 == "gene" and c1 and c2:
                    pairs.add((str(c2), str(c1)))
            return pairs
        except Exception:
            return set()

    def lookup(self, term: str) -> EntityLookupResult:
        """
        Resolve an entity term strictly against entities and synonyms tables.
        Returns:
            - resolved: exactly one canonical entity matches
            - ambiguous: multiple entities or colliding types match
            - unresolved: no entity matches
        """
        cleaned = term.strip()
        if not cleaned:
            return EntityLookupResult(query=term, status="unresolved")

        cleaned_lower = cleaned.lower()
        norm_key = normalize_search_term(cleaned)

        # 1. Exact match on entities table
        # Avoid string escaping issues by parameterized queries
        entities_sql = f"""
            SELECT canonical_id
            FROM '{self.entities_path.as_posix()}'
            WHERE LOWER(canonical_id) = ?
               OR LOWER(primary_source_id) = ?
               OR LOWER(display_name) = ?
               OR normalized_name = ?
               OR (entity_type = 'gene' AND LOWER(gene_symbol) = ?)
        """
        matched_rows = self._con.execute(
            entities_sql, [cleaned_lower, cleaned_lower, cleaned_lower, norm_key, cleaned_lower]
        ).fetchall()

        matched_canonical_ids = {row[0] for row in matched_rows}

        # 2. Match on synonyms table
        syn_sql = f"""
            SELECT canonical_id
            FROM '{self.synonyms_path.as_posix()}'
            WHERE LOWER(synonym_text) = ?
               OR normalized_synonym = ?
        """
        syn_rows = self._con.execute(syn_sql, [cleaned_lower, norm_key]).fetchall()
        for s in syn_rows:
            matched_canonical_ids.add(s[0])

        # 3. Star-allele spacing key route: evaluate whenever '*' is in norm_key and union
        if "*" in norm_key:
            star_spacing_key = re.sub(r"\s*\*\s*", " *", norm_key)
            star_ent_sql = f"""
                SELECT canonical_id
                FROM '{self.entities_path.as_posix()}'
                WHERE normalized_name = ?
                   OR LOWER(display_name) = ?
            """
            for row in self._con.execute(
                star_ent_sql, [star_spacing_key, star_spacing_key]
            ).fetchall():
                matched_canonical_ids.add(row[0])

        if not matched_canonical_ids:
            return EntityLookupResult(query=term, status="unresolved")

        # Fetch details for matched canonical IDs and deduplicate by canonical_id
        # The same ID from clinpgx and cpic counts once, with all sources in provenance
        ids_list = list(matched_canonical_ids)
        placeholders = ", ".join(["?"] * len(ids_list))
        src_col = "source_name" if self._entities_has_source_name else "NULL AS source_name"
        fetch_sql = f"""
            SELECT canonical_id, entity_type, primary_source_id, display_name,
                   normalized_name, is_drug, gene_symbol, defined_by, is_ambiguous, {src_col}
            FROM '{self.entities_path.as_posix()}'
            WHERE canonical_id IN ({placeholders})
        """
        all_matches = self._con.execute(fetch_sql, ids_list).fetchall()

        by_cid: Dict[str, Dict[str, Any]] = {}
        for r in all_matches:
            cid = r[0]
            src = r[9] if len(r) > 9 and r[9] else None
            if cid not in by_cid:
                by_cid[cid] = {
                    "canonical_id": r[0],
                    "entity_type": r[1],
                    "primary_source_id": r[2],
                    "display_name": r[3],
                    "normalized_name": r[4],
                    "is_drug": bool(r[5]),
                    "gene_symbol": r[6] if r[6] else None,
                    "defined_by": r[7],
                    "is_ambiguous": bool(r[8]),
                    "sources": set(),
                }
            if src:
                by_cid[cid]["sources"].add(src)

        candidates: List[ResolvedEntity] = []
        types_set = set()
        for cid in sorted(by_cid.keys()):
            data = by_cid[cid]
            srcs = sorted(list(data["sources"]))
            candidates.append(
                ResolvedEntity(
                    canonical_id=data["canonical_id"],
                    entity_type=data["entity_type"],
                    primary_source_id=data["primary_source_id"],
                    display_name=data["display_name"],
                    normalized_name=data["normalized_name"],
                    is_drug=data["is_drug"],
                    gene_symbol=data["gene_symbol"],
                    defined_by=data["defined_by"],
                    is_ambiguous=data["is_ambiguous"],
                    provenance=srcs,
                    sources=srcs,
                    resolved_via="text",
                )
            )
            types_set.add(data["entity_type"])

        # If exactly 1 distinct canonical ID matched: resolved
        if len(candidates) == 1:
            return EntityLookupResult(
                query=term,
                status="resolved",
                canonical_id=candidates[0].canonical_id,
                candidate_types=[candidates[0].entity_type],
                candidates=candidates,
                resolved_via="text",
            )

        # Multiple candidates: ambiguous with all candidate entities and types
        return EntityLookupResult(
            query=term,
            status="ambiguous",
            canonical_id=None,
            candidate_types=sorted(list(types_set)),
            candidates=candidates,
            resolved_via="text",
        )

    def lookup_by_canonical_ids(self, canonical_ids: List[str]) -> List[EntityLookupResult]:
        """Directly resolve entities by explicit canonical IDs (e.g. from entity_hints)."""
        clean_ids = [c.strip() for c in canonical_ids if c and c.strip()]
        if not clean_ids:
            return []
        unique_ids = list(dict.fromkeys(clean_ids))
        placeholders = ", ".join(["?"] * len(unique_ids))
        src_col = "source_name" if self._entities_has_source_name else "NULL AS source_name"
        sql = f"""
            SELECT canonical_id, entity_type, primary_source_id, display_name,
                   normalized_name, is_drug, gene_symbol, defined_by, is_ambiguous, {src_col}
            FROM '{self.entities_path.as_posix()}'
            WHERE canonical_id IN ({placeholders})
        """
        rows = self._con.execute(sql, unique_ids).fetchall()
        by_cid: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            cid = r[0]
            src = r[9] if len(r) > 9 and r[9] else None
            if cid not in by_cid:
                by_cid[cid] = {
                    "canonical_id": r[0],
                    "entity_type": r[1],
                    "primary_source_id": r[2],
                    "display_name": r[3],
                    "normalized_name": r[4],
                    "is_drug": bool(r[5]),
                    "gene_symbol": r[6] if r[6] else None,
                    "defined_by": r[7],
                    "is_ambiguous": bool(r[8]),
                    "sources": set(),
                }
            if src:
                by_cid[cid]["sources"].add(src)

        out: List[EntityLookupResult] = []
        for cid in unique_ids:
            if cid in by_cid:
                data = by_cid[cid]
                srcs = sorted(list(data["sources"]))
                ent = ResolvedEntity(
                    canonical_id=data["canonical_id"],
                    entity_type=data["entity_type"],
                    primary_source_id=data["primary_source_id"],
                    display_name=data["display_name"],
                    normalized_name=data["normalized_name"],
                    is_drug=data["is_drug"],
                    gene_symbol=data["gene_symbol"],
                    defined_by=data["defined_by"],
                    is_ambiguous=data["is_ambiguous"],
                    provenance=srcs,
                    sources=srcs,
                    resolved_via="hint",
                )
                out.append(
                    EntityLookupResult(
                        query=ent.display_name,
                        status="resolved",
                        canonical_id=ent.canonical_id,
                        candidate_types=[ent.entity_type],
                        candidates=[ent],
                        resolved_via="hint",
                    )
                )
        return out

    def is_valid_canonical_id(self, canonical_id: str) -> bool:
        """Check if a canonical ID exists in the entities table."""
        if not canonical_id or not self.entities_path.exists():
            return False
        sql = f"SELECT 1 FROM '{self.entities_path.as_posix()}' WHERE canonical_id = ? LIMIT 1"
        try:
            return bool(self._con.execute(sql, [canonical_id.strip()]).fetchone())
        except Exception:
            return False

    @staticmethod
    def _is_short_alpha_gene_filtered(cand_token: str, candidate: ResolvedEntity) -> bool:
        """
        Return True if `candidate` is a purely alphabetic <=6-letter gene symbol
        matched by a free-text token that was NOT typed in exact uppercase.
        Chemical names and symbols with digits/punctuation are unaffected.
        """
        if candidate.entity_type.lower() != "gene":
            return False
        sym = (candidate.gene_symbol or candidate.display_name or "").strip()
        if not sym or not _SHORT_ALPHA_GENE_RE.fullmatch(sym):
            return False
        if " " in cand_token:
            return False
        if cand_token.lower() != sym.lower():
            return False
        return cand_token != sym.upper()

    def extract_and_resolve_entities_with_notes(
        self,
        text: str,
        entity_hints: Optional[List[str]] = None,
    ) -> Tuple[List[EntityLookupResult], List[str]]:
        """
        Extract candidate tokens and 2-grams from a free-text question and resolve them.
        Enforces:
        - Explicit QUESTION_WORD_STOPLIST for non-uppercase prose tokens
        - Purely alphabetic gene symbols <= 6 letters resolve from free text only when typed
          in exact uppercase (or supplied via entity_hints)
        Returns (resolved_results, possible_gene_names_lowercase).
        """
        words = [w.strip("?,.:;\"'()[]{}") for w in text.split()]
        words = [w for w in words if len(w) >= 2]

        # Check 1-grams and 2-grams
        candidates_to_check: List[str] = []
        for i, w1 in enumerate(words):
            if not (w1.lower() in QUESTION_WORD_STOPLIST and not w1.isupper()):
                candidates_to_check.append(w1)
            if i + 1 < len(words):
                w2 = words[i + 1]
                w1_skip = w1.lower() in QUESTION_WORD_STOPLIST and not w1.isupper()
                w2_skip = w2.lower() in QUESTION_WORD_STOPLIST and not w2.isupper()
                if not w1_skip or not w2_skip:
                    candidates_to_check.append(f"{w1} {w2}")

        results: List[EntityLookupResult] = []
        seen_canonical_ids: Set[str] = set()
        hinted_words_lower: Set[str] = set()
        resolved_chemical_ids: Set[str] = set()
        possible_gene_names_lowercase: List[str] = []
        seen_lower_gene_words: Set[str] = set()

        hints_by_cid: Dict[str, EntityLookupResult] = {}
        hint_surface_forms: Dict[str, Set[str]] = defaultdict(set)
        matched_hint_cids: Set[str] = set()
        if entity_hints:
            clean_hints = list(dict.fromkeys(h.strip() for h in entity_hints if h and h.strip()))
            for h_res in self.lookup_by_canonical_ids(clean_hints):
                if h_res.canonical_id:
                    cid = h_res.canonical_id
                    hints_by_cid[cid] = h_res
                    for c in h_res.candidates:
                        hinted_words_lower.add(c.display_name.lower())
                        if c.gene_symbol:
                            hinted_words_lower.add(c.gene_symbol.lower())
                        if c.entity_type.lower() == "chemical":
                            resolved_chemical_ids.add(c.canonical_id)
                        # Add entity's own names to hint_surface_forms
                        own_names = [c.display_name, c.normalized_name, c.primary_source_id]
                        if c.entity_type.lower() == "gene" and c.gene_symbol:
                            own_names.append(c.gene_symbol)
                        for name in own_names:
                            if name:
                                s = str(name).lower().strip()
                                hint_surface_forms[cid].add(s)
                                hint_surface_forms[cid].add(normalize_search_term(s))
                                hint_surface_forms[cid].add(re.sub(r"\s*\*\s*", "*", s))
                                hint_surface_forms[cid].add(re.sub(r"\s*\*\s*", " *", s))

            # Query synonyms for hinted entities to capture surface form variants
            if self.synonyms_path.exists() and hints_by_cid:
                placeholders = ", ".join(["?"] * len(hints_by_cid))
                syn_sql = f"""
                    SELECT canonical_id, synonym_text, normalized_synonym
                    FROM '{self.synonyms_path.as_posix()}'
                    WHERE canonical_id IN ({placeholders})
                """
                syn_rows = self._con.execute(syn_sql, list(hints_by_cid.keys())).fetchall()
                for s_cid, syn_text, norm_syn in syn_rows:
                    if syn_text:
                        s = str(syn_text).lower().strip()
                        hint_surface_forms[s_cid].add(s)
                        hint_surface_forms[s_cid].add(normalize_search_term(s))
                        hint_surface_forms[s_cid].add(re.sub(r"\s*\*\s*", "*", s))
                        hint_surface_forms[s_cid].add(re.sub(r"\s*\*\s*", " *", s))
                    if norm_syn:
                        s = str(norm_syn).lower().strip()
                        hint_surface_forms[s_cid].add(s)

        # Pass 1: Lookup candidates, resolve non-filtered entities, and collect resolved chemicals
        raw_lookups: List[
            Tuple[str, List[ResolvedEntity], List[ResolvedEntity], EntityLookupResult]
        ] = []
        for cand in candidates_to_check:
            res = self.lookup(cand)
            if res.status == "unresolved":
                continue

            # Check if this candidate matches an explicit entity_hint
            matching_hint_cid = None
            if hints_by_cid:
                cand_low = cand.lower().strip()
                cand_norm = normalize_search_term(cand)
                cand_star = re.sub(r"\s*\*\s*", "*", cand_low)
                cand_star_space = re.sub(r"\s*\*\s*", " *", cand_low)
                cand_keys = {cand_low, cand_norm, cand_star, cand_star_space}

                for h_cid, s_forms in hint_surface_forms.items():
                    if cand_keys.intersection(s_forms):
                        matching_hint_cid = h_cid
                        break

                if not matching_hint_cid:
                    cand_cids = {c.canonical_id for c in res.candidates}
                    if res.canonical_id:
                        cand_cids.add(res.canonical_id)
                    for h_cid in hints_by_cid:
                        if h_cid in cand_cids:
                            matching_hint_cid = h_cid
                            break

            if matching_hint_cid:
                # Valid hint injected as resolved for ITS surface form only
                h_res = hints_by_cid[matching_hint_cid]
                matched_hint_cids.add(matching_hint_cid)
                if matching_hint_cid not in seen_canonical_ids:
                    seen_canonical_ids.add(matching_hint_cid)
                    override = None
                    if res.status == "resolved" and res.canonical_id != matching_hint_cid:
                        override = {"hint_id": matching_hint_cid, "text_id": res.canonical_id}
                    base_cand = h_res.candidates[0] if h_res.candidates else None
                    cand_type = (
                        h_res.candidate_types[0] if h_res.candidate_types else "unknown"
                    )
                    hint_cand = (
                        base_cand.model_copy(deep=True)
                        if base_cand
                        else ResolvedEntity(
                            canonical_id=matching_hint_cid,
                            entity_type=cand_type,
                            primary_source_id=matching_hint_cid,
                            display_name=cand,
                            normalized_name=cand.lower(),
                            is_drug=False,
                            defined_by="hint",
                            is_ambiguous=False,
                            resolved_via="hint",
                        )
                    )
                    hint_cand.resolved_via = "hint"
                    hint_cand.hint_overrode_text = override
                    results.append(
                        EntityLookupResult(
                            query=cand,
                            status="resolved",
                            canonical_id=matching_hint_cid,
                            candidate_types=[hint_cand.entity_type],
                            candidates=[hint_cand],
                            resolved_via="hint",
                            hint_overrode_text=override,
                        )
                    )
                    if hint_cand.entity_type.lower() == "chemical":
                        resolved_chemical_ids.add(matching_hint_cid)
                continue

            immediate_kept: List[ResolvedEntity] = []
            pending_lower_genes: List[ResolvedEntity] = []
            for c in res.candidates:
                if self._is_short_alpha_gene_filtered(cand, c):
                    pending_lower_genes.append(c)
                else:
                    immediate_kept.append(c)

            if len(immediate_kept) == 1 and immediate_kept[0].entity_type.lower() == "chemical":
                resolved_chemical_ids.add(immediate_kept[0].canonical_id)

            raw_lookups.append((cand, immediate_kept, pending_lower_genes, res))

        # Pass 2: Evaluate lowercase <=6-alpha gene rule against resolved chemicals or CPIC list
        for cand, immediate_kept, pending_lower_genes, res in raw_lookups:
            kept_candidates: List[ResolvedEntity] = list(immediate_kept)
            filtered_gene = False
            for c in pending_lower_genes:
                sym_up = (c.gene_symbol or c.display_name or "").strip().upper()
                in_cpic = sym_up in self._cpic_genes
                has_chem_edge = bool(resolved_chemical_ids) and any(
                    (c.canonical_id, chem_cid) in self._gene_chemical_edges
                    for chem_cid in resolved_chemical_ids
                )
                if in_cpic or has_chem_edge:
                    kept_candidates.append(c)
                else:
                    filtered_gene = True

            if not kept_candidates:
                if (
                    filtered_gene
                    and cand.lower() not in hinted_words_lower
                    and cand.lower() not in seen_lower_gene_words
                ):
                    seen_lower_gene_words.add(cand.lower())
                    possible_gene_names_lowercase.append(cand.lower())
                continue

            if len(kept_candidates) == 1:
                only = kept_candidates[0]
                if only.canonical_id not in seen_canonical_ids:
                    seen_canonical_ids.add(only.canonical_id)
                    results.append(
                        EntityLookupResult(
                            query=cand,
                            status="resolved",
                            canonical_id=only.canonical_id,
                            candidate_types=[only.entity_type],
                            candidates=[only],
                            resolved_via="text",
                        )
                    )
            else:
                kept_types = sorted({c.entity_type for c in kept_candidates})
                results.append(
                    EntityLookupResult(
                        query=cand,
                        status="ambiguous",
                        canonical_id=None,
                        candidate_types=kept_types,
                        candidates=kept_candidates,
                        resolved_via="text",
                    )
                )

        # Any hints that did not match a surface form token in the question are injected directly
        if hints_by_cid:
            for h_cid, h_res in hints_by_cid.items():
                if h_cid not in matched_hint_cids and h_cid not in seen_canonical_ids:
                    seen_canonical_ids.add(h_cid)
                    h_res.resolved_via = "hint"
                    results.append(h_res)

        return results, possible_gene_names_lowercase

    def extract_and_resolve_entities(
        self,
        text: str,
        entity_hints: Optional[List[str]] = None,
    ) -> List[EntityLookupResult]:
        """Backward-compatible wrapper returning resolved/ambiguous entities from free text."""
        results, _ = self.extract_and_resolve_entities_with_notes(
            text, entity_hints=entity_hints
        )
        return results

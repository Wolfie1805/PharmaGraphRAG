"""
Entity lookup module: exact and normalized-key matching over entities and synonyms.
Enforces strict ambiguous/unresolved status and disallows fuzzy matching.
"""

import re
from pathlib import Path
from typing import List, Optional, Set, Tuple

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


class EntityLookupResult(BaseModel):
    """Outcome of entity lookup for a query mention."""

    query: str
    status: str = Field(description="'resolved', 'ambiguous', or 'unresolved'")
    canonical_id: Optional[str] = None
    candidate_types: List[str] = Field(default_factory=list)
    candidates: List[ResolvedEntity] = Field(default_factory=list)


class EntityLookupService:
    """Exact and normalized-key entity resolution service over Parquet tables."""

    def __init__(self, processed_dir: Path = Path("data/processed")):
        self.processed_dir = processed_dir
        self.entities_path = processed_dir / "entities.parquet"
        self.synonyms_path = processed_dir / "synonyms.parquet"
        self._con = duckdb.connect(":memory:")

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
            SELECT canonical_id, entity_type, primary_source_id, display_name,
                   normalized_name, is_drug, gene_symbol, defined_by, is_ambiguous
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

        # 3. Star-allele whitespace normalization fallback (lookup key only; stored names unchanged)
        if not matched_canonical_ids and "*" in norm_key:
            star_key = re.sub(r"\s*\*\s*", "*", norm_key)
            star_ent_sql = f"""
                SELECT canonical_id
                FROM '{self.entities_path.as_posix()}'
                WHERE CONTAINS(normalized_name, '*')
                  AND REGEXP_REPLACE(normalized_name, '\\s*\\*\\s*', '*', 'g') = ?
            """
            for row in self._con.execute(star_ent_sql, [star_key]).fetchall():
                matched_canonical_ids.add(row[0])

            star_syn_sql = f"""
                SELECT canonical_id
                FROM '{self.synonyms_path.as_posix()}'
                WHERE CONTAINS(normalized_synonym, '*')
                  AND REGEXP_REPLACE(normalized_synonym, '\\s*\\*\\s*', '*', 'g') = ?
            """
            for row in self._con.execute(star_syn_sql, [star_key]).fetchall():
                matched_canonical_ids.add(row[0])

        if not matched_canonical_ids:
            return EntityLookupResult(query=term, status="unresolved")

        # Fetch full details for all matched canonical IDs
        ids_list = list(matched_canonical_ids)
        placeholders = ", ".join(["?"] * len(ids_list))
        fetch_sql = f"""
            SELECT canonical_id, entity_type, primary_source_id, display_name,
                   normalized_name, is_drug, gene_symbol, defined_by, is_ambiguous
            FROM '{self.entities_path.as_posix()}'
            WHERE canonical_id IN ({placeholders})
        """
        all_matches = self._con.execute(fetch_sql, ids_list).fetchall()

        candidates: List[ResolvedEntity] = []
        types_set = set()
        for r in all_matches:
            candidates.append(
                ResolvedEntity(
                    canonical_id=r[0],
                    entity_type=r[1],
                    primary_source_id=r[2],
                    display_name=r[3],
                    normalized_name=r[4],
                    is_drug=bool(r[5]),
                    gene_symbol=r[6] if r[6] else None,
                    defined_by=r[7],
                    is_ambiguous=bool(r[8]),
                )
            )
            types_set.add(r[1])

        # If exactly 1 distinct canonical ID matched: resolved
        if len(candidates) == 1:
            return EntityLookupResult(
                query=term,
                status="resolved",
                canonical_id=candidates[0].canonical_id,
                candidate_types=[candidates[0].entity_type],
                candidates=candidates,
            )

        # Multiple candidates: ambiguous with all candidate entities and types
        return EntityLookupResult(
            query=term,
            status="ambiguous",
            canonical_id=None,
            candidate_types=sorted(list(types_set)),
            candidates=candidates,
        )

    def lookup_by_canonical_ids(self, canonical_ids: List[str]) -> List[EntityLookupResult]:
        """Directly resolve entities by explicit canonical IDs (e.g. from entity_hints)."""
        clean_ids = [c.strip() for c in canonical_ids if c and c.strip()]
        if not clean_ids:
            return []
        unique_ids = list(dict.fromkeys(clean_ids))
        placeholders = ", ".join(["?"] * len(unique_ids))
        sql = f"""
            SELECT canonical_id, entity_type, primary_source_id, display_name,
                   normalized_name, is_drug, gene_symbol, defined_by, is_ambiguous
            FROM '{self.entities_path.as_posix()}'
            WHERE canonical_id IN ({placeholders})
        """
        rows = self._con.execute(sql, unique_ids).fetchall()
        by_cid = {}
        for r in rows:
            ent = ResolvedEntity(
                canonical_id=r[0],
                entity_type=r[1],
                primary_source_id=r[2],
                display_name=r[3],
                normalized_name=r[4],
                is_drug=bool(r[5]),
                gene_symbol=r[6] if r[6] else None,
                defined_by=r[7],
                is_ambiguous=bool(r[8]),
            )
            by_cid[ent.canonical_id] = ent

        out: List[EntityLookupResult] = []
        for cid in unique_ids:
            ent = by_cid.get(cid)
            if ent is not None:
                out.append(
                    EntityLookupResult(
                        query=ent.display_name,
                        status="resolved",
                        canonical_id=ent.canonical_id,
                        candidate_types=[ent.entity_type],
                        candidates=[ent],
                    )
                )
        return out

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
        possible_gene_names_lowercase: List[str] = []
        seen_lower_gene_words: Set[str] = set()

        if entity_hints:
            for h_res in self.lookup_by_canonical_ids(entity_hints):
                if h_res.canonical_id and h_res.canonical_id not in seen_canonical_ids:
                    seen_canonical_ids.add(h_res.canonical_id)
                    results.append(h_res)
                    for c in h_res.candidates:
                        hinted_words_lower.add(c.display_name.lower())
                        if c.gene_symbol:
                            hinted_words_lower.add(c.gene_symbol.lower())

        for cand in candidates_to_check:
            res = self.lookup(cand)
            if res.status == "unresolved":
                continue

            # Filter candidates according to the uppercase <=6-alpha gene rule
            kept_candidates: List[ResolvedEntity] = []
            filtered_gene = False
            for c in res.candidates:
                if self._is_short_alpha_gene_filtered(cand, c):
                    filtered_gene = True
                else:
                    kept_candidates.append(c)

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
                    )
                )

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

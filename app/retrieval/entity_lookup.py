"""
Entity lookup module: exact and normalized-key matching over entities and synonyms.
Enforces strict ambiguous/unresolved status and disallows fuzzy matching.
"""

from pathlib import Path
from typing import List, Optional

import duckdb
from pydantic import BaseModel, Field

from app.normalization.normalize import normalize_search_term


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

    def extract_and_resolve_entities(self, text: str) -> List[EntityLookupResult]:
        """
        Extract candidate tokens and n-grams from a free-text question and resolve them.
        """
        # Split on whitespace/punctuation to find potential entity terms
        words = [w.strip("?,.:;\"'()[]{}") for w in text.split()]
        words = [w for w in words if len(w) >= 2]

        STOPWORDS = {
            "the", "is", "between", "and", "or", "in", "of", "to", "for",
            "with", "a", "an", "what", "how", "why", "who", "which", "are",
            "does", "relationship"
        }

        # Check 1-grams and 2-grams
        candidates_to_check = []
        for i in range(len(words)):
            w1 = words[i]
            if w1.lower() not in STOPWORDS:
                candidates_to_check.append(w1)
            if i + 1 < len(words):
                w2 = words[i+1]
                if w1.lower() not in STOPWORDS or w2.lower() not in STOPWORDS:
                    candidates_to_check.append(f"{w1} {w2}")

        results: List[EntityLookupResult] = []
        seen_canonical_ids = set()
        for cand in candidates_to_check:
            res = self.lookup(cand)
            if res.status == "resolved" and res.canonical_id:
                if res.canonical_id not in seen_canonical_ids:
                    seen_canonical_ids.add(res.canonical_id)
                    results.append(res)
            elif res.status == "ambiguous":
                results.append(res)

        return results

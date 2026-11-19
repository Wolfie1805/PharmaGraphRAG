"""
Answer synthesis service orchestrating guards, retrieval, bundling,
checks, generation modes (extractive, ollama, mock), query modes (overview, detail),
and citation verification.
"""

import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import duckdb

from app.generation.adapter import BaseLLMClient, get_llm_client
from app.generation.checks import detect_evidence_conflicts, evaluate_evidence_sufficiency
from app.generation.config import GenerationConfig
from app.generation.contracts import (
    AskResponse,
    DetailSections,
    EvidenceBundle,
    EvidenceItem,
    OverviewData,
    OverviewRow,
    PromptTemplateItem,
    SuggestedNextItem,
    VariantFindingGroup,
    VariantFindingItem,
)
from app.generation.guard import InputGuard
from app.generation.verifier import CitationVerifier
from app.retrieval.brand_index import BrandIndex, BrandLookupData
from app.retrieval.pipeline import RetrievalPipeline

# Module-level in-memory cache for variant annotations
_VAR_DRUG_ANN_CACHE: Optional[Dict[str, Dict[str, str]]] = None


def _get_var_drug_ann_cache() -> Dict[str, Dict[str, str]]:
    global _VAR_DRUG_ANN_CACHE
    if _VAR_DRUG_ANN_CACHE is not None:
        return _VAR_DRUG_ANN_CACHE
    cache: Dict[str, Dict[str, str]] = {}
    zip_path = Path("data/raw/clinpgx/20261030_79ff97e7/variantAnnotations.zip")
    if zip_path.exists():
        try:
            with zipfile.ZipFile(zip_path) as z:
                if "var_drug_ann.tsv" in z.namelist():
                    with z.open("var_drug_ann.tsv") as f:
                        reader = csv.DictReader(
                            io.TextIOWrapper(f, encoding="utf-8"), delimiter="\t"
                        )
                        for row in reader:
                            cache[row["Variant Annotation ID"]] = row
        except Exception:
            pass
    _VAR_DRUG_ANN_CACHE = cache
    return _VAR_DRUG_ANN_CACHE


# Module-level in-memory cache for guideline issuing body (guideline.source)
_GUIDELINE_SOURCE_CACHE: Optional[Dict[str, str]] = None


def _get_guideline_source_cache() -> Dict[str, str]:
    global _GUIDELINE_SOURCE_CACHE
    if _GUIDELINE_SOURCE_CACHE is not None:
        return _GUIDELINE_SOURCE_CACHE
    cache: Dict[str, str] = {}
    zip_path = Path("data/raw/clinpgx/20261030_79ff97e7/guidelineAnnotations.json.zip")
    if zip_path.exists():
        try:
            with zipfile.ZipFile(zip_path) as z:
                for name in z.namelist():
                    if name.endswith(".json"):
                        data = json.loads(z.read(name).decode("utf-8"))
                        g = data.get("guideline") if isinstance(data, dict) else None
                        if isinstance(g, dict):
                            gid = str(g.get("id") or "").strip()
                            src = str(g.get("source") or "").strip()
                            if gid and src:
                                cache[gid] = src
        except Exception:
            pass
    _GUIDELINE_SOURCE_CACHE = cache
    return _GUIDELINE_SOURCE_CACHE


SUPPORTED_PROMPT_TEMPLATES: List[PromptTemplateItem] = [
    PromptTemplateItem(
        name="A medicine",
        shape="[Medicine]",
        template="[Medicine name]",
        example="clopidogrel",
        description="Overview of all gene interactions and evidence for a medicine.",
    ),
    PromptTemplateItem(
        name="A gene",
        shape="[Gene]",
        template="[Gene symbol]",
        example="CYP2C19",
        description="Overview of all medicine interactions and evidence for a gene.",
    ),
    PromptTemplateItem(
        name="A gene and a medicine",
        shape="[Gene] [Medicine]",
        template="[Gene] [Medicine]",
        example="CYP2C19 clopidogrel",
        description="Detailed clinical guidelines, drug labels, and variant findings for a pair.",
    ),
    PromptTemplateItem(
        name="A variant and a medicine",
        shape="[Variant] [Medicine]",
        template="[Variant/rsID] [Medicine]",
        example="rs4244285 clopidogrel",
        description="Detailed evidence and findings for a specific variant-drug association.",
    ),
]


class AnswerService:
    """End-to-end question answering service."""

    def __init__(
        self,
        config: Optional[GenerationConfig] = None,
        retrieval_pipeline: Optional[RetrievalPipeline] = None,
        llm_client: Optional[BaseLLMClient] = None,
        mock_llm: bool = False,
    ):
        self.config = config or GenerationConfig()
        self.retrieval_pipeline = retrieval_pipeline or RetrievalPipeline()
        if llm_client is not None:
            self.llm_client = llm_client
        else:
            self.llm_client = get_llm_client(self.config, mock=mock_llm)
        self.brand_index = BrandIndex()
        # Pre-warm in-memory caches so first request never times out
        _get_var_drug_ann_cache()
        _get_guideline_source_cache()

    def get_stats_summary(self) -> Dict[str, Any]:
        """Return full meaning-search coverage summary per source_type."""
        coverage_fn = getattr(self.retrieval_pipeline, "get_meaning_coverage", None)
        if not callable(coverage_fn):
            return {
                "per_source_type": {},
                "is_partial": True,
                "covered_source_types": [],
                "complete_source_types": [],
            }
        return coverage_fn() or {
            "per_source_type": {},
            "is_partial": True,
            "covered_source_types": [],
            "complete_source_types": [],
        }

    def _coverage_metadata(self) -> tuple[Dict[str, Any], List[str]]:
        """Return (meaning_coverage_dict, partial_flags) safely for real or mock pipelines."""
        summary = self.get_stats_summary()
        per_type = summary.get("per_source_type", {})
        partial_flags: List[str] = []
        if summary.get("is_partial"):
            covered = summary.get("covered_source_types", [])
            covered_label = ",".join(covered) if covered else "none"
            partial_flags.append(f"meaning_search_partial:{covered_label}")
        return per_type, partial_flags

    def _resolve_query_mode(
        self,
        is_refused: bool,
        resolved_entities: List[Any],
        has_ambiguous: bool,
    ) -> str:
        """
        Decide query mode strictly from resolved entity types:
        - medicine_overview (one chemical)
        - gene_overview (one gene)
        - pair_detail (gene + chemical)
        - variant_detail (variant or allele + chemical, with or without its gene)
        - variant_overview (variant or allele alone)
        - unrecognized
        - ambiguous
        - refused
        """
        if is_refused:
            return "refused"
        if has_ambiguous:
            return "ambiguous"

        resolved_cids = [
            e for e in resolved_entities if getattr(e, "status", "") == "resolved"
        ]
        if not resolved_cids:
            return "unrecognized"

        chems = []
        genes = []
        variants = []
        for ent in resolved_cids:
            etype = ""
            if getattr(ent, "candidates", None) and ent.candidates:
                etype = ent.candidates[0].entity_type.lower()
            elif getattr(ent, "candidate_types", None) and ent.candidate_types:
                etype = ent.candidate_types[0].lower()
            elif getattr(ent, "entity_type", None):
                etype = ent.entity_type.lower()

            if etype == "chemical":
                chems.append(ent)
            elif etype == "gene":
                genes.append(ent)
            elif etype in {"variant", "snv", "haplotype", "cnv"}:
                variants.append(ent)

        if variants and chems:
            return "variant_detail"
        if genes and chems:
            return "pair_detail"
        if chems and not genes and not variants:
            return "medicine_overview"
        if genes and not chems and not variants:
            return "gene_overview"
        if variants and not chems:
            return "variant_overview"
        return "unrecognized"

    def _build_overview(
        self,
        target_entity: Any,
        offset: int = 0,
        limit: int = 20,
    ) -> OverviewData:
        """
        Build overview rows from relationships.parquet plus chunk counts
        from chunks_v2.parquet and linked paper counts.
        """
        target_cid = target_entity.canonical_id
        target_name = (
            target_entity.candidates[0].display_name
            if getattr(target_entity, "candidates", None) and target_entity.candidates
            else getattr(target_entity, "query", target_cid)
        )
        target_type = (
            target_entity.candidates[0].entity_type.lower()
            if getattr(target_entity, "candidates", None) and target_entity.candidates
            else ""
        )

        rel_path = "data/processed/relationships.parquet"
        chunks_path = "data/processed/chunks_v2.parquet"

        con = duckdb.connect(":memory:")
        if target_type == "chemical":
            q = f"""
                SELECT
                    entity1_canonical_id, entity1_name, entity1_type,
                    entity2_canonical_id, entity2_name, entity2_type,
                    association, pmids
                FROM '{rel_path}'
                WHERE (entity1_canonical_id = $1 AND lower(entity2_type) = 'gene')
                   OR (entity2_canonical_id = $1 AND lower(entity1_type) = 'gene')
            """
        elif target_type == "gene":
            q = f"""
                SELECT
                    entity1_canonical_id, entity1_name, entity1_type,
                    entity2_canonical_id, entity2_name, entity2_type,
                    association, pmids
                FROM '{rel_path}'
                WHERE (entity1_canonical_id = $1 AND lower(entity2_type) = 'chemical')
                   OR (entity2_canonical_id = $1 AND lower(entity1_type) = 'chemical')
            """
        else:
            q = f"""
                SELECT
                    entity1_canonical_id, entity1_name, entity1_type,
                    entity2_canonical_id, entity2_name, entity2_type,
                    association, pmids
                FROM '{rel_path}'
                WHERE entity1_canonical_id = $1 OR entity2_canonical_id = $1
            """

        edge_rows = con.execute(q, [target_cid]).fetchall()

        # Batch calculate chunk counts for all connected entities
        chunk_counts_raw = con.execute(f"""
            WITH target_chunks AS (
                SELECT source_type, unnest(entity_ids) AS eid
                FROM '{chunks_path}'
                WHERE list_contains(entity_ids, $1)
            )
            SELECT eid, source_type, count(1) AS cnt
            FROM target_chunks
            GROUP BY eid, source_type
        """, [target_cid]).fetchall()

        counts_by_eid: Dict[str, Dict[str, int]] = {}
        for eid, stype, cnt in chunk_counts_raw:
            if eid not in counts_by_eid:
                counts_by_eid[eid] = {}
            counts_by_eid[eid][stype] = cnt

        seen_others: Set[str] = set()
        rows: List[OverviewRow] = []

        for r in edge_rows:
            e1_cid, e1_name, e1_type, e2_cid, e2_name, e2_type, assoc, pmids_raw = r
            if e1_cid == target_cid:
                other_cid, other_name, other_type = e2_cid, e2_name, e2_type
            else:
                other_cid, other_name, other_type = e1_cid, e1_name, e1_type

            if other_cid in seen_others:
                continue
            seen_others.add(other_cid)

            pmids_set: Set[str] = set()
            if pmids_raw:
                for item in pmids_raw:
                    for p in str(item).split(";"):
                        p_clean = p.strip()
                        if p_clean:
                            pmids_set.add(p_clean)

            c_map = counts_by_eid.get(other_cid, {})
            ann_cnt = c_map.get("annotation", 0)
            drug_cnt = c_map.get("drug_label", 0)
            guide_cnt = c_map.get("guideline", 0)
            curated_cnt = ann_cnt + drug_cnt + guide_cnt
            papers_cnt = len(pmids_set)

            if target_type == "chemical":
                chem_id, chem_name = target_cid, target_name
                gene_id, gene_name = other_cid, other_name
            else:
                chem_id, chem_name = other_cid, other_name
                gene_id, gene_name = target_cid, target_name

            row = OverviewRow(
                target_id=target_cid,
                target_name=target_name,
                target_type=target_type,
                other_id=other_cid,
                other_name=other_name,
                other_type=other_type,
                chemical_id=chem_id,
                chemical_name=chem_name,
                gene_id=gene_id,
                gene_name=gene_name,
                association=assoc or "associated",
                annotation_count=ann_cnt,
                drug_label_count=drug_cnt,
                guideline_count=guide_cnt,
                curated_count=curated_cnt,
                linked_papers_count=papers_cnt,
            )
            rows.append(row)

        rows.sort(key=lambda r: (-r.curated_count, r.other_name.lower()))
        total_count = len(rows)
        paged_rows = rows[offset : offset + limit]

        return OverviewData(
            total_count=total_count,
            offset=offset,
            limit=limit,
            rows=paged_rows,
        )

    def _build_suggested_next(
        self,
        resolved_entities: List[Any],
        query_mode: str,
    ) -> List[SuggestedNextItem]:
        """
        Produce up to 5 suggested follow-up searches from relationship edges
        touching resolved entities, in deterministic order.
        """
        resolved_cids = [
            e.canonical_id
            for e in resolved_entities
            if getattr(e, "status", "") == "resolved" and getattr(e, "canonical_id", None)
        ]
        if not resolved_cids:
            return []

        cids_set = set(resolved_cids)
        placeholders = ",".join([f"'{c}'" for c in resolved_cids])
        con = duckdb.connect(":memory:")
        rel_path = "data/processed/relationships.parquet"
        q = f"""
            SELECT
                entity1_canonical_id, entity1_name, entity1_type,
                entity2_canonical_id, entity2_name, entity2_type,
                pmids
            FROM '{rel_path}'
            WHERE entity1_canonical_id IN ({placeholders})
               OR entity2_canonical_id IN ({placeholders})
        """
        rows = con.execute(q).fetchall()

        seen_labels: Set[str] = set()
        candidates: List[Dict[str, Any]] = []

        for e1_cid, e1_name, e1_type, e2_cid, e2_name, e2_type, pmids in rows:
            if e1_cid in cids_set and e2_cid in cids_set:
                continue
            if e1_cid not in cids_set and e2_cid not in cids_set:
                continue

            if e1_cid in cids_set:
                anchor_cid, anchor_name = e1_cid, e1_name
                other_cid, other_name = e2_cid, e2_name
            else:
                anchor_cid, anchor_name = e2_cid, e2_name
                other_cid, other_name = e1_cid, e1_name

            label = (
                f"{other_name} + {anchor_name}"
                if anchor_name.lower() in ("clopidogrel", "warfarin")
                else f"{anchor_name} + {other_name}"
            )
            if label in seen_labels:
                continue
            seen_labels.add(label)

            pmids_count = 0
            if pmids:
                for item in pmids:
                    pmids_count += len(str(item).split(";"))

            candidates.append({
                "label": label,
                "entity_ids": [anchor_cid, other_cid],
                "score": pmids_count,
            })

        candidates.sort(key=lambda c: (-c["score"], c["label"]))
        return [
            SuggestedNextItem(label=c["label"], entity_ids=c["entity_ids"])
            for c in candidates[:5]
        ]

    def _build_sections(
        self,
        evidence_items: List[EvidenceItem],
        resolved_entities: List[Any],
        query_mode: str = "pair_detail",
    ) -> DetailSections:
        """
        Group evidence items into guidelines, drug_labels, variant_findings
        (with raw structured columns mapped), linked_papers, and recorded_relationships.
        """
        guidelines = [it for it in evidence_items if it.source_type == "guideline"]
        drug_labels = [it for it in evidence_items if it.source_type == "drug_label"]
        linked_papers = [it for it in evidence_items if it.source_type == "pubmed"]
        recorded_relationships = [
            it for it in evidence_items if it.source_type == "relationship_record"
        ]

        variant_ents = [
            e
            for e in resolved_entities
            if getattr(e, "status", None) == "resolved"
            and getattr(e, "candidates", None)
            and e.candidates[0].entity_type.lower()
            in ("variant", "haplotype", "snv", "allele")
        ]
        chem_ents = [
            e
            for e in resolved_entities
            if getattr(e, "status", None) == "resolved"
            and getattr(e, "candidates", None)
            and e.candidates[0].entity_type.lower() == "chemical"
        ]
        gene_ents = [
            e
            for e in resolved_entities
            if getattr(e, "status", None) == "resolved"
            and getattr(e, "candidates", None)
            and e.candidates[0].entity_type.lower() == "gene"
        ]

        guidelines_label: Optional[str] = None
        drug_labels_label: Optional[str] = None

        chunks_path = "data/processed/chunks_v2.parquet"
        rel_path = "data/processed/relationships.parquet"

        effective_gene_cid = gene_ents[0].canonical_id if gene_ents else None
        effective_chem_cid = chem_ents[0].canonical_id if chem_ents else None

        # If in variant_detail mode without explicit gene resolved,
        # resolve parent gene from variant candidate
        if query_mode == "variant_detail" and not effective_gene_cid and variant_ents:
            v_sym = getattr(variant_ents[0].candidates[0], "gene_symbol", None)
            if v_sym:
                con = duckdb.connect(":memory:")
                g_match = con.execute(
                    f"""
                    SELECT entity1_canonical_id FROM '{rel_path}'
                    WHERE lower(entity1_name) = lower($1)
                    UNION
                    SELECT entity2_canonical_id FROM '{rel_path}'
                    WHERE lower(entity2_name) = lower($1)
                    LIMIT 1
                    """,
                    [v_sym],
                ).fetchall()
                if g_match:
                    effective_gene_cid = g_match[0][0]

        # For variant_detail: label guidelines and drug labels as gene-medicine pair records
        if query_mode == "variant_detail":
            pair_note = "Records for this gene-medicine pair (not variant-specific)"
            guidelines_label = pair_note
            drug_labels_label = pair_note

        # Surface gene-medicine pair guidelines (and drug labels for variant_detail)
        # from chunks_v2.parquet when not already present in top retrieval items
        if effective_gene_cid and effective_chem_cid and (
            not guidelines or (query_mode == "variant_detail" and not drug_labels)
        ):
            con = duckdb.connect(":memory:")
            pair_chunks = con.execute(
                f"""
                SELECT source_type, source_id, title, content, entity_ids
                FROM '{chunks_path}'
                WHERE source_type IN ('guideline', 'drug_label')
                  AND list_contains(entity_ids, $1)
                  AND list_contains(entity_ids, $2)
            """,
                [effective_gene_cid, effective_chem_cid],
            ).fetchall()
            for stype, sid, title, content, eids in pair_chunks:
                item = EvidenceItem(
                    source_type=stype,
                    source_id=str(sid),
                    title=title or "",
                    chunk_text=content or "",
                    matched_entities=list(eids) if eids else [],
                )
                if stype == "guideline" and not any(
                    it.source_id == str(sid) for it in guidelines
                ):
                    guidelines.append(item)
                elif (
                    query_mode == "variant_detail"
                    and stype == "drug_label"
                    and not any(it.source_id == str(sid) for it in drug_labels)
                ):
                    drug_labels.append(item)

        # All linked papers present in corpus
        all_linked_papers: List[EvidenceItem] = []
        if effective_gene_cid and effective_chem_cid:
            con = duckdb.connect(":memory:")
            pmids_raw = con.execute(
                f"""
                SELECT pmids FROM '{rel_path}'
                WHERE (entity1_canonical_id = $1 AND entity2_canonical_id = $2)
                   OR (entity2_canonical_id = $1 AND entity1_canonical_id = $2)
            """,
                [effective_chem_cid, effective_gene_cid],
            ).fetchall()
            rel_pmids = []
            for (plist,) in pmids_raw:
                if plist:
                    for p in plist:
                        for item in str(p).split(";"):
                            clean = item.strip()
                            if clean and clean not in rel_pmids:
                                rel_pmids.append(clean)
            if rel_pmids:
                placeholders = ", ".join([f"'{p}'" for p in rel_pmids])
                corpus_papers = con.execute(f"""
                    SELECT source_id, title, min(content)
                    FROM '{chunks_path}'
                    WHERE source_type = 'pubmed' AND source_id IN ({placeholders})
                    GROUP BY source_id, title
                    ORDER BY source_id DESC
                """).fetchall()
                for sid, title, content in corpus_papers:
                    all_linked_papers.append(
                        EvidenceItem(
                            source_type="pubmed",
                            source_id=str(sid),
                            title=title or "",
                            chunk_text=content or "",
                            matched_entities=[effective_gene_cid, effective_chem_cid],
                        )
                    )

        # Attach guideline.source issuing body from guidelineAnnotations JSON when present
        guideline_src_cache = _get_guideline_source_cache()
        for g_item in guidelines:
            issuing_body = guideline_src_cache.get(g_item.source_id)
            if issuing_body:
                g_item.provenance = {**g_item.provenance, "guideline.source": issuing_body}

        ann_cache = _get_var_drug_ann_cache()
        ann_items = [it for it in evidence_items if it.source_type == "annotation"]

        groups_map: Dict[str, List[VariantFindingItem]] = {}
        for it in ann_items:
            raw = ann_cache.get(it.source_id, {})
            tag = (
                raw.get("Variant/Haplotypes")
                or raw.get("Alleles")
                or "Other variants"
            ).strip()
            if not tag:
                tag = "Other variants"

            sig = (raw.get("Significance") or "").strip() or None
            pheno = (raw.get("Phenotype Category") or "").strip() or None
            direct = (raw.get("Direction of effect") or "").strip() or None
            pop = (raw.get("Population types") or "").strip() or None
            pmid = (raw.get("PMID") or "").strip() or None

            source_cols = {
                "significance": "Significance",
                "phenotype_category": "Phenotype Category",
                "direction_of_effect": "Direction of effect",
                "population_types": "Population types",
            }

            vf_item = VariantFindingItem(
                source_id=it.source_id,
                title=it.title,
                sentence=it.chunk_text,
                significance=sig,
                phenotype_category=pheno,
                direction_of_effect=direct,
                population_types=pop,
                pmid=pmid,
                source_columns=source_cols,
            )
            if tag not in groups_map:
                groups_map[tag] = []
            groups_map[tag].append(vf_item)

        variant_groups: List[VariantFindingGroup] = []
        for tag, f_list in groups_map.items():
            variant_groups.append(
                VariantFindingGroup(
                    variant_tag=tag,
                    display_name=tag,
                    findings=f_list,
                )
            )
        variant_groups.sort(key=lambda g: (-len(g.findings), g.variant_tag.lower()))

        return DetailSections(
            guidelines=guidelines,
            drug_labels=drug_labels,
            variant_findings=variant_groups,
            linked_papers=linked_papers,
            all_linked_papers=all_linked_papers,
            recorded_relationships=recorded_relationships,
            guidelines_label=guidelines_label,
            drug_labels_label=drug_labels_label,
        )

    def answer_question(
        self,
        question: str,
        entity_hints: Optional[List[str]] = None,
        overview_offset: int = 0,
        overview_limit: int = 20,
    ) -> AskResponse:
        """
        Execute full answer generation pipeline:
        1. Input Guard (refuses advice, dosing, clearly non-biomedical queries with 0 calls)
        2. Retrieval Pipeline (hybrid retrieval + graph lookup + RRF)
        3. Unrecognized-entity & zero-grounded-evidence gates
        4. Query mode determination (overview vs detail)
        5. Evidence Bundling & Basic Checks (sufficiency, conflicts)
        6. Answer Generation (extractive, ollama, or mock)
        7. Citation Verification (always executed)
        """
        meaning_coverage, partial_flags = self._coverage_metadata()

        # 1. Input Guard
        is_refused, category, message = InputGuard.evaluate(question)
        if is_refused:
            return AskResponse(
                question=question,
                answer=message or "Query was refused.",
                claims=[],
                related_claims=[],
                evidence_bundle=EvidenceBundle(
                    query=question,
                    items=[],
                    total_items=0,
                    has_sufficient_evidence=False,
                ),
                resolved_entities=[],
                flags=["refused", f"refusal_{category}"],
                removed_claims_count=0,
                disclaimer_text=self.config.disclaimer_text,
                answer_mode=self.config.llm_mode,
                meaning_coverage=meaning_coverage,
                llm_calls=0,
                network_calls=0,
                builder_calls=0,
                query_mode="refused",
                overview=None,
                sections=None,
                suggested_next=[],
                prompt_templates=[],
            )

        # 2. Retrieval Pipeline
        if entity_hints is not None:
            retrieval_res = self.retrieval_pipeline.query(question, entity_hints=entity_hints)
        else:
            retrieval_res = self.retrieval_pipeline.query(question)

        if not meaning_coverage and getattr(retrieval_res, "meaning_coverage", None):
            meaning_coverage = retrieval_res.meaning_coverage

        # Format resolved entities for API response
        resolved_entities_dicts: List[Dict[str, Any]] = []
        for ent in retrieval_res.resolved_entities:
            ent_dict: Dict[str, Any] = {
                "name": ent.query,
                "query": ent.query,
                "status": ent.status,
            }
            if ent.canonical_id:
                ent_dict["canonical_id"] = ent.canonical_id
            if ent.candidate_types:
                ent_dict["candidate_types"] = ent.candidate_types
            if ent.candidates:
                ent_dict["candidates"] = [c.model_dump() for c in ent.candidates]
            if getattr(ent, "resolved_via", None):
                ent_dict["resolved_via"] = ent.resolved_via
            if getattr(ent, "hint_overrode_text", None):
                ent_dict["hint_overrode_text"] = ent.hint_overrode_text
            resolved_entities_dicts.append(ent_dict)

        resolved_cids = list(
            dict.fromkeys(
                e.canonical_id
                for e in retrieval_res.resolved_entities
                if e.status == "resolved" and e.canonical_id
            )
        )
        has_ambiguous = any(e.status == "ambiguous" for e in retrieval_res.resolved_entities)

        # Check brand matches
        brand_matches = self.brand_index.search(question)

        # Ambiguity resolution: if both a brand match and a ClinPGx entity match exist for the same text
        if (resolved_cids or has_ambiguous) and brand_matches:
            brand_candidates = [
                {
                    "canonical_id": f"nrces:brand:{b['brand_id']}",
                    "entity_type": "Indian brand (NRCeS)",
                    "primary_source_id": b["brand_id"],
                    "display_name": b["brand_name"],
                    "normalized_name": b["normalized_name"],
                    "is_drug": True,
                    "defined_by": "NRCeS",
                    "is_ambiguous": False,
                }
                for b in brand_matches[:10]
            ]
            if resolved_entities_dicts:
                for e_dict in resolved_entities_dicts:
                    e_dict["status"] = "ambiguous"
                    existing_cands = e_dict.get("candidates", [])
                    e_dict["candidates"] = existing_cands + brand_candidates
                    types = set(e_dict.get("candidate_types", []))
                    types.add("Indian brand (NRCeS)")
                    e_dict["candidate_types"] = sorted(list(types))
            else:
                resolved_entities_dicts.append({
                    "name": question,
                    "query": question,
                    "status": "ambiguous",
                    "candidate_types": ["Indian brand (NRCeS)"],
                    "candidates": brand_candidates,
                })

            flags: List[str] = ["ambiguous_entity", "insufficient_evidence"]
            return AskResponse(
                question=question,
                answer=(
                    "Multiple matching entities and Indian brands were found in the database. "
                    "Please select a specific candidate below."
                ),
                claims=[],
                related_claims=[],
                evidence_bundle=EvidenceBundle(
                    query=question,
                    resolved_entity_ids=[],
                    items=[],
                    total_items=0,
                    has_sufficient_evidence=False,
                ),
                resolved_entities=resolved_entities_dicts,
                flags=flags,
                removed_claims_count=0,
                disclaimer_text=self.config.disclaimer_text,
                answer_mode=self.config.llm_mode,
                meaning_coverage=meaning_coverage,
                llm_calls=0,
                network_calls=0,
                builder_calls=0,
                query_mode="ambiguous",
                overview=None,
                sections=None,
                brands=None,
                suggested_next=[],
                prompt_templates=[],
            )

        flags: List[str] = []
        if has_ambiguous:
            flags.append("ambiguous_entity")
        for low_word in getattr(retrieval_res, "possible_gene_names_lowercase", []) or []:
            flags.append(f"possible_gene_name_lowercase:{low_word}")

        # 2b. Gate Stage B1: Ambiguous entity found
        if has_ambiguous:
            flags.append("insufficient_evidence")
            ambiguous_answer = (
                "Multiple matching entities were found in the database. "
                "Please select a specific candidate below."
            )
            return AskResponse(
                question=question,
                answer=ambiguous_answer,
                claims=[],
                related_claims=[],
                evidence_bundle=EvidenceBundle(
                    query=question,
                    resolved_entity_ids=[],
                    items=[],
                    total_items=0,
                    has_sufficient_evidence=False,
                ),
                resolved_entities=resolved_entities_dicts,
                flags=flags,
                removed_claims_count=0,
                disclaimer_text=self.config.disclaimer_text,
                answer_mode=self.config.llm_mode,
                meaning_coverage=meaning_coverage,
                llm_calls=0,
                network_calls=0,
                builder_calls=0,
                query_mode="ambiguous",
                overview=None,
                sections=None,
                suggested_next=[],
                prompt_templates=[],
            )

        # 2c. Gate Stage B1: No resolved or ambiguous entity found
        if not resolved_cids and not has_ambiguous:
            if brand_matches:
                brand_data = self.brand_index.get_brand_lookup_data(
                    question, offset=overview_offset, limit=10
                )
                disclaimer = (
                    "This only identifies ingredients. It does not say what the medicine is for "
                    "or how to take it. Lack of ClinPGx records does not mean a medicine is safe."
                )
                return AskResponse(
                    question=question,
                    answer="Indian brand name match from NRCeS Common Drug Codes for India.",
                    claims=[],
                    related_claims=[],
                    evidence_bundle=EvidenceBundle(
                        query=question,
                        resolved_entity_ids=[],
                        items=[],
                        total_items=0,
                        has_sufficient_evidence=False,
                    ),
                    resolved_entities=[],
                    flags=["brand_lookup"],
                    removed_claims_count=0,
                    disclaimer_text=disclaimer,
                    answer_mode="brand_lookup",
                    meaning_coverage=meaning_coverage,
                    llm_calls=0,
                    network_calls=0,
                    builder_calls=0,
                    query_mode="brand_lookup",
                    overview=None,
                    sections=None,
                    brands=brand_data,
                    suggested_next=[],
                    prompt_templates=[],
                )

            flags.append("unrecognized_entity")
            unrecognized_message = (
                "No recognized gene, variant or chemical was found in your question in the "
                "ClinPGx data used by this prototype. Supported query formats are shown below."
            )
            return AskResponse(
                question=question,
                answer=unrecognized_message,
                claims=[],
                related_claims=[],
                evidence_bundle=EvidenceBundle(
                    query=question,
                    resolved_entity_ids=[],
                    items=[],
                    total_items=0,
                    has_sufficient_evidence=False,
                ),
                resolved_entities=resolved_entities_dicts,
                flags=flags,
                removed_claims_count=0,
                disclaimer_text=self.config.disclaimer_text,
                answer_mode=self.config.llm_mode,
                meaning_coverage=meaning_coverage,
                llm_calls=0,
                network_calls=0,
                builder_calls=0,
                query_mode="unrecognized",
                overview=None,
                sections=None,
                suggested_next=[],
                prompt_templates=SUPPORTED_PROMPT_TEMPLATES,
            )

        # 2d. Determine Query Mode
        query_mode = self._resolve_query_mode(False, retrieval_res.resolved_entities, False)

        # Handle Overview Modes (medicine_overview, gene_overview, variant_overview)
        if query_mode in ("medicine_overview", "gene_overview", "variant_overview"):
            flags.extend(partial_flags)
            if query_mode == "medicine_overview":
                target_ent = [
                    e for e in retrieval_res.resolved_entities
                    if (
                        e.status == "resolved"
                        and e.candidates
                        and e.candidates[0].entity_type.lower() == "chemical"
                    )
                ][0]
                t_name = (
                    target_ent.candidates[0].display_name
                    if target_ent.candidates
                    else target_ent.query
                )
                answer_text = (
                    f"Showing gene interactions and evidence summary for medicine '{t_name}'."
                )
            elif query_mode == "gene_overview":
                target_ent = [
                    e for e in retrieval_res.resolved_entities
                    if (
                        e.status == "resolved"
                        and e.candidates
                        and e.candidates[0].entity_type.lower() == "gene"
                    )
                ][0]
                t_name = (
                    target_ent.candidates[0].display_name
                    if target_ent.candidates
                    else target_ent.query
                )
                answer_text = (
                    f"Showing medicine interactions and evidence summary for gene '{t_name}'."
                )
            else:
                target_ent = [
                    e for e in retrieval_res.resolved_entities if e.status == "resolved"
                ][0]
                t_name = (
                    target_ent.candidates[0].display_name
                    if target_ent.candidates
                    else target_ent.query
                )
                answer_text = (
                    f"Showing interactions and evidence summary for variant '{t_name}'."
                )

            overview_data = self._build_overview(
                target_ent, offset=overview_offset, limit=overview_limit
            )
            suggested = self._build_suggested_next(
                retrieval_res.resolved_entities, query_mode
            )

            bundle = EvidenceBundle(
                query=question,
                resolved_entity_ids=[target_ent.canonical_id],
                items=[],
                total_items=0,
                has_sufficient_evidence=True,
            )
            return AskResponse(
                question=question,
                answer=answer_text,
                claims=[],
                related_claims=[],
                evidence_bundle=bundle,
                resolved_entities=resolved_entities_dicts,
                flags=flags,
                removed_claims_count=0,
                disclaimer_text=self.config.disclaimer_text,
                answer_mode=self.config.llm_mode,
                meaning_coverage=meaning_coverage,
                llm_calls=0,
                network_calls=0,
                builder_calls=0,
                query_mode=query_mode,
                overview=overview_data,
                sections=None,
                suggested_next=suggested,
                prompt_templates=[],
            )

        # 3. Evidence Bundling for Detail Modes (pair_detail, variant_detail)
        evidence_items: List[EvidenceItem] = []
        hits = getattr(retrieval_res, "top_evidence", None) or getattr(retrieval_res, "results", [])
        for r in hits:
            source_id = str(r.source_id)
            content_text = getattr(r, "content", None) or getattr(r, "chunk_text", "")
            score_val = getattr(r, "rrf_score", None) or getattr(r, "fused_score", 0.0)
            paths = getattr(r, "found_by_paths", None) or getattr(r, "retrieval_paths", [])
            matched = getattr(r, "matched_entities", [])
            item_prov = dict(getattr(r, "provenance", {}) or {})

            # Map associated graph edges for this chunk
            attached_edges = [
                edge.model_dump()
                for edge in retrieval_res.graph_edges
                if source_id in edge.pmids
                or edge.entity1_name.lower() in content_text.lower()
                or edge.entity2_name.lower() in content_text.lower()
            ]

            item = EvidenceItem(
                source_id=source_id,
                source_type=r.source_type,
                title=r.title,
                date=r.date,
                date_precision=r.date_precision,
                chunk_text=content_text,
                entities=r.entity_ids,
                matched_entities=matched,
                retrieval_paths=paths,
                score=score_val,
                graph_edges=attached_edges,
                provenance=item_prov,
            )
            evidence_items.append(item)

        # Add all retrieved graph edges to evidence bundle as relationship_record items
        for edge in retrieval_res.graph_edges:
            rel_item = EvidenceItem(
                source_id=edge.relationship_id,
                source_type="relationship_record",
                title=f"Association: {edge.entity1_name} - {edge.entity2_name}",
                chunk_text=(
                    f"Relationship record {edge.relationship_id}: "
                    f"{edge.entity1_name} ({edge.entity1_type}) "
                    f"has association '{edge.association}' with "
                    f"{edge.entity2_name} ({edge.entity2_type})."
                ),
                entities=[edge.entity1_canonical_id, edge.entity2_canonical_id],
                matched_entities=[edge.entity1_canonical_id, edge.entity2_canonical_id],
                retrieval_paths=["graph_lookup"],
                score=0.05,
                graph_edges=[edge.model_dump()],
                provenance={
                    "raw_file_name": "relationships.parquet",
                    "raw_file_sha256": edge.raw_file_sha256 or "",
                    "relationship_id": edge.relationship_id,
                    "association": edge.association,
                },
            )
            evidence_items.append(rel_item)

        bundle = EvidenceBundle(
            query=question,
            resolved_entity_ids=resolved_cids,
            items=evidence_items,
            total_items=len(evidence_items),
        )

        # Build sections and suggested next
        sections = self._build_sections(
            evidence_items, retrieval_res.resolved_entities, query_mode=query_mode
        )
        suggested = self._build_suggested_next(retrieval_res.resolved_entities, query_mode)

        # 4. Basic Checks & Gate Stage B2
        has_grounded_chunk = any(
            bool(it.matched_entities)
            for it in evidence_items
            if it.source_type != "relationship_record"
        )
        has_graph_edges = len(retrieval_res.graph_edges) > 0

        is_sufficient, _suff_reason = evaluate_evidence_sufficiency(
            bundle,
            min_items=self.config.min_evidence_items,
            min_top_score=self.config.min_top_score,
        )
        if not has_grounded_chunk and not has_graph_edges:
            is_sufficient = False
            bundle.has_sufficient_evidence = False

        if not is_sufficient:
            flags.append("insufficient_evidence")
            grounded_items = [it for it in bundle.items if bool(it.matched_entities)]
            bundle.items = grounded_items
            bundle.total_items = len(grounded_items)

        has_conflicts, _conflict_info = detect_evidence_conflicts(bundle)
        if has_conflicts:
            flags.append("conflicts_detected")

        flags.extend(partial_flags)

        # If evidence is insufficient, return answer without calling generation
        if not is_sufficient:
            fallback_answer = (
                f"Insufficient evidence was retrieved to reliably answer '{question}'. "
                f"Retrieved {bundle.total_items} grounded items "
                f"(minimum required: {self.config.min_evidence_items})."
            )
            return AskResponse(
                question=question,
                answer=fallback_answer,
                claims=[],
                related_claims=[],
                evidence_bundle=bundle,
                resolved_entities=resolved_entities_dicts,
                flags=flags,
                removed_claims_count=0,
                disclaimer_text=self.config.disclaimer_text,
                answer_mode=self.config.llm_mode,
                meaning_coverage=meaning_coverage,
                llm_calls=0,
                network_calls=0,
                builder_calls=0,
                query_mode=query_mode,
                overview=None,
                sections=sections,
                suggested_next=suggested,
                prompt_templates=[],
            )

        # 5. Answer Generation
        gen_out, extra_flags = self.llm_client.generate_answer(question, bundle)
        flags.extend(extra_flags)

        # 6. Citation Verification
        verified_claims, removed_main = CitationVerifier.verify(gen_out.claims, bundle)
        verified_related, removed_related = CitationVerifier.verify(
            gen_out.related_claims, bundle
        )
        removed_count = removed_main + removed_related
        if removed_count > 0:
            flags.append(f"unverified_citations_removed_{removed_count}")

        # Assemble final answer
        final_answer = gen_out.answer
        if gen_out.conflicts and gen_out.conflicts != "None noted.":
            final_answer += f"\n\nConflicts: {gen_out.conflicts}"
        if gen_out.limitations and gen_out.limitations != "None noted.":
            final_answer += f"\n\nLimitations: {gen_out.limitations}"

        return AskResponse(
            question=question,
            answer=final_answer,
            claims=verified_claims,
            related_claims=verified_related,
            evidence_bundle=bundle,
            resolved_entities=resolved_entities_dicts,
            flags=flags,
            removed_claims_count=removed_count,
            disclaimer_text=self.config.disclaimer_text,
            answer_mode=gen_out.answer_mode,
            meaning_coverage=meaning_coverage,
            llm_calls=self.llm_client.llm_calls,
            network_calls=self.llm_client.network_calls,
            builder_calls=self.llm_client.builder_calls,
            query_mode=query_mode,
            overview=None,
            sections=sections,
            suggested_next=suggested,
            prompt_templates=[],
        )

"""
Answer synthesis service orchestrating guards, retrieval, bundling,
checks, generation modes (extractive, ollama, mock), and citation verification.
"""

from typing import Any, Dict, List, Optional

from app.generation.adapter import BaseLLMClient, get_llm_client
from app.generation.checks import detect_evidence_conflicts, evaluate_evidence_sufficiency
from app.generation.config import GenerationConfig
from app.generation.contracts import (
    AskResponse,
    EvidenceBundle,
    EvidenceItem,
)
from app.generation.guard import InputGuard
from app.generation.verifier import CitationVerifier
from app.retrieval.pipeline import RetrievalPipeline


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

    def answer_question(
        self,
        question: str,
        entity_hints: Optional[List[str]] = None,
    ) -> AskResponse:
        """
        Execute full answer generation pipeline:
        1. Input Guard (refuses advice, dosing, clearly non-biomedical queries with 0 calls)
        2. Retrieval Pipeline (hybrid retrieval + graph lookup + RRF)
        3. Unrecognized-entity & zero-grounded-evidence gates
        4. Evidence Bundling & Basic Checks (sufficiency, conflicts)
        5. Answer Generation (extractive, ollama, or mock)
        6. Citation Verification (always executed)
        """
        meaning_coverage, partial_flags = self._coverage_metadata()

        # 1. Input Guard
        is_refused, category, message = InputGuard.evaluate(question)
        if is_refused:
            return AskResponse(
                question=question,
                answer=message or "Query was refused.",
                claims=[],
                evidence_bundle=EvidenceBundle(
                    query=question,
                    items=[],
                    total_items=0,
                    has_sufficient_evidence=False,
                ),
                resolved_entities=[],
                flags=["refused", f"refusal_{category}", *partial_flags],
                removed_claims_count=0,
                disclaimer_text=self.config.disclaimer_text,
                answer_mode=self.config.llm_mode,
                meaning_coverage=meaning_coverage,
                llm_calls=0,
                network_calls=0,
                builder_calls=0,
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
            resolved_entities_dicts.append(ent_dict)

        resolved_cids = list(
            dict.fromkeys(
                e.canonical_id
                for e in retrieval_res.resolved_entities
                if e.status == "resolved" and e.canonical_id
            )
        )
        has_ambiguous = any(e.status == "ambiguous" for e in retrieval_res.resolved_entities)

        flags: List[str] = []
        if has_ambiguous:
            flags.append("ambiguous_entity")
        for low_word in getattr(retrieval_res, "possible_gene_names_lowercase", []) or []:
            flags.append(f"possible_gene_name_lowercase:{low_word}")

        # 2b. Gate Stage B1: No resolved or ambiguous entity found
        if not resolved_cids and not has_ambiguous:
            flags.append("unrecognized_entity")
            flags.extend(partial_flags)
            unrecognized_message = (
                "No recognized gene, variant or chemical was found in your question in the "
                "ClinPGx data used by this prototype. Check the spelling or try the generic "
                "(ingredient) name, often printed in the composition line on the medicine strip."
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
            )

        # 3. Evidence Bundling
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

        # 4. Basic Checks & Gate Stage B2
        # Gate Stage B2: Resolved entities present, but 0 retrieved chunks carry any
        # resolved entity ID AND there are 0 graph edges -> insufficient evidence.
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
            # Exclude ungrounded hits when insufficient_evidence is set
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
        )

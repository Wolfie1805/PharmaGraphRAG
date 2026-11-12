export interface EntityCandidate {
  canonical_id: string;
  entity_type: string;
  primary_source_id: string;
  display_name: string;
  normalized_name: string;
  is_drug: boolean;
  gene_symbol?: string | null;
  defined_by: string;
  is_ambiguous: boolean;
}

export interface ResolvedEntity {
  name: string;
  query: string;
  status: 'resolved' | 'ambiguous' | 'unresolved';
  canonical_id?: string;
  candidate_types?: string[];
  candidates?: EntityCandidate[];
}

export interface EvidenceItem {
  source_id: string;
  source_type: string;
  title: string;
  date?: string;
  date_precision?: string;
  chunk_text: string;
  entities: string[];
  matched_entities?: string[];
  retrieval_paths: string[];
  score: number;
  graph_edges?: Record<string, unknown>[];
  provenance?: Record<string, unknown>;
}

export interface EvidenceBundle {
  query: string;
  resolved_entity_ids?: string[];
  items: EvidenceItem[];
  total_items: number;
  has_sufficient_evidence: boolean;
  conflicts_detected: boolean;
  conflict_details?: string | null;
}

export interface Claim {
  text: string;
  source_ids: string[];
}

export interface MeaningSourceCoverage {
  indexed: number;
  expected: number;
  complete: boolean;
}

export interface MeaningCoverageStats {
  per_source_type: Record<string, MeaningSourceCoverage>;
  is_partial: boolean;
  covered_source_types: string[];
  complete_source_types: string[];
}

export interface AskResponse {
  question: string;
  answer: string;
  claims: Claim[];
  related_claims?: Claim[];
  evidence_bundle: EvidenceBundle;
  resolved_entities: ResolvedEntity[];
  flags: string[];
  removed_claims_count: number;
  disclaimer_text: string;
  answer_mode: string;
  meaning_coverage?: Record<string, MeaningSourceCoverage>;
  llm_calls: number;
  network_calls: number;
  builder_calls: number;
}

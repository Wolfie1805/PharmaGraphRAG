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
  entity_type?: string;
  candidate_types?: string[];
  candidates?: EntityCandidate[];
  resolved_via?: 'hint' | 'text';
  hint_overrode_text?: {
    hint_id: string;
    text_id: string;
  };
}

export interface SuggestItem {
  canonical_id: string;
  display_label: string;
  matched_alias: string;
  match_kind: 'exact' | 'prefix' | 'word_prefix' | 'substring' | 'typo';
  entity_type: string;
  sort_group: 'chemical' | 'gene' | 'variant' | 'allele' | 'other';
  is_ambiguous?: boolean;
  candidate_count?: number;
}

export interface ReadyMadeSearch {
  query: string;
  gene: string;
  chemical: string;
}

export interface SuggestResponse {
  suggestions: SuggestItem[];
  searches: ReadyMadeSearch[];
}

export interface DemoQuestion {
  id: string;
  category: string;
  question: string;
  expected_entities: string[];
  verified_by_human?: boolean;
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


export interface LicenseNote {
  quote: string;
  location: string;
}

export interface PubMedQueryInfo {
  pair_id: string;
  query: string;
  esearch_count: number;
  retrieval_date: string;
}

export interface SourceMetadata {
  name: string;
  description: string;
  license?: string;
  site_footer_license?: string;
  archive_bundled_license?: string;
  discrepancy_unresolved?: boolean;
  working_assumption?: string;
  date_checked: string;
  license_notes?: LicenseNote[];
  pubmed_queries?: PubMedQueryInfo[];
}

export interface RawFileRun {
  run_id: string;
  count: number;
  bytes: number;
}

export interface RawFilesSummary {
  clinpgx?: {
    source_name: string;
    count: number;
    bytes: number;
    release_label: string;
  };
  pubmed?: {
    source_name: string;
    count: number;
    bytes: number;
    release_label: string;
    runs?: {
      full?: RawFileRun;
      pilot?: RawFileRun;
    };
  };
}

export interface ChunkTypeSummary {
  total: number;
  with_any_entity: number;
  with_variant_or_allele: number;
}

export interface PapersSummary {
  count: number;
  year_min?: number;
  year_max?: number;
  year_range?: string;
  with_abstracts: number;
}

export interface BenchmarkSummary {
  question_count: number;
  run_date: string;
  qdrant_path?: string;
  rule_checks?: {
    guard: string;
    ambiguity: string;
  };
  retrieval_proxy?: {
    hit_at_10: number;
    precision_at_10: number;
    mrr: number;
    not_a_quality_score: boolean;
    verified_by_human: boolean;
  };
}

export interface SiteStats {
  generated_at?: string | null;
  git?: {
    commit?: string | null;
    latest_tag?: string | null;
    dirty?: boolean | null;
  } | null;
  raw_files?: RawFilesSummary | null;
  processed_tables?: Record<string, number | null> | null;
  entities_by_type?: Record<string, number> | null;
  relationships?: {
    total: number;
    dangling: number;
  } | null;
  chunks_by_source_type?: Record<string, ChunkTypeSummary> | null;
  papers?: PapersSummary | null;
  retrieval?: {
    path_names: string[];
    embedding_model: string;
    meaning_coverage?: Record<string, MeaningSourceCoverage> | null;
    default_answer_mode: string;
  } | null;
  sources?: SourceMetadata[] | null;
  tests?: {
    pytest_collected?: number | null;
    vitest_collected?: number | null;
  } | null;
  benchmark?: BenchmarkSummary | null;
}

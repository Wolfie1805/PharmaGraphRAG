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

export interface OverviewRow {
  target_id: string;
  target_name: string;
  target_type: string;
  other_id: string;
  other_name: string;
  other_type: string;
  chemical_id: string;
  chemical_name: string;
  gene_id: string;
  gene_name: string;
  association: string;
  annotation_count: number;
  drug_label_count: number;
  guideline_count: number;
  curated_count: number;
  linked_papers_count: number;
}

export interface OverviewData {
  total_count: number;
  offset: number;
  limit: number;
  rows: OverviewRow[];
}

export interface VariantFindingItem {
  source_id: string;
  title: string;
  sentence: string;
  significance?: string | null;
  phenotype_category?: string | null;
  direction_of_effect?: string | null;
  population_types?: string | null;
  pmid?: string | null;
  source_columns?: Record<string, string>;
}

export interface VariantFindingGroup {
  variant_tag: string;
  display_name: string;
  canonical_id?: string | null;
  findings: VariantFindingItem[];
}

export interface DetailSections {
  guidelines: EvidenceItem[];
  drug_labels: EvidenceItem[];
  variant_findings: VariantFindingGroup[];
  linked_papers: EvidenceItem[];
  all_linked_papers?: EvidenceItem[];
  recorded_relationships: EvidenceItem[];
  guidelines_label?: string;
  drug_labels_label?: string;
}

export interface SuggestedNextItem {
  label: string;
  entity_ids: string[];
}

export interface PromptTemplateItem {
  name: string;
  shape: string;
  template: string;
  example: string;
  description: string;
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
  query_mode?: string;
  overview?: OverviewData | null;
  sections?: DetailSections | null;
  suggested_next?: SuggestedNextItem[];
  prompt_templates?: PromptTemplateItem[];
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

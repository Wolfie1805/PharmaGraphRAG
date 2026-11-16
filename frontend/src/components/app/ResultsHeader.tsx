import React from 'react';
import { ResolvedEntity, SuggestedNextItem } from '../../types';

interface ResultsHeaderProps {
  question: string;
  queryMode: string;
  resolvedEntities: ResolvedEntity[];
  suggestedNext?: SuggestedNextItem[];
  onSelectSuggestion: (query: string, hints?: string[]) => void;
}

const MODE_METADATA: Record<string, { label: string; explanation: string; badgeClass: string }> = {
  medicine_overview: {
    label: 'Medicine overview',
    explanation: 'Curated gene interactions, chunk counts across sources, and linked papers for this medicine.',
    badgeClass: 'badge-medicine',
  },
  gene_overview: {
    label: 'Gene overview',
    explanation: 'Curated medicine interactions, chunk counts across sources, and linked papers for this gene.',
    badgeClass: 'badge-gene',
  },
  pair_detail: {
    label: 'Pair detail',
    explanation: 'Clinical guidelines, drug label annotations, and clinical variant findings for this pair.',
    badgeClass: 'badge-pair',
  },
  variant_detail: {
    label: 'Variant detail',
    explanation: 'Clinical findings, effect direction, and citations for this specific variant and medicine.',
    badgeClass: 'badge-variant',
  },
  variant_overview: {
    label: 'Variant overview',
    explanation: 'Curated relationships and evidence findings recorded for this variant alone.',
    badgeClass: 'badge-variant',
  },
  ambiguous: {
    label: 'Ambiguous entity',
    explanation: 'Multiple distinct entities matched this query. Please choose a specific candidate below.',
    badgeClass: 'badge-ambiguous',
  },
  unrecognized: {
    label: 'Unrecognized query',
    explanation: 'No recognized chemical, gene, or variant was matched in the data archive.',
    badgeClass: 'badge-unrecognized',
  },
  refused: {
    label: 'Clinical guard notice',
    explanation: 'This prototype provides pharmacogenomic evidence retrieval rather than prescriptive guidance.',
    badgeClass: 'badge-refused',
  },
};

export const ResultsHeader: React.FC<ResultsHeaderProps> = ({
  question,
  queryMode,
  resolvedEntities,
  suggestedNext = [],
  onSelectSuggestion,
}) => {
  const modeInfo = MODE_METADATA[queryMode] || {
    label: queryMode.replace(/_/g, ' '),
    explanation: 'Biomedical query results and evidence synthesis.',
    badgeClass: 'badge-default',
  };

  const resolvedOnly = (resolvedEntities || []).filter(
    (e) => e.status === 'resolved' && e.canonical_id
  );

  return (
    <header className="results-header-panel" aria-label="Query Summary and Context">
      {/* 1. You asked */}
      <div className="results-query-row">
        <span className="results-row-label">You asked:</span>
        <span className="results-query-text">"{question}"</span>
      </div>

      {/* 2. We understood */}
      {resolvedOnly.length > 0 && (
        <div className="results-understood-row">
          <span className="results-row-label">We understood:</span>
          <div className="results-chips-list" role="list">
            {resolvedOnly.map((ent) => {
              const etype = ent.candidates?.[0]?.entity_type || ent.entity_type || 'Entity';
              const isAllele = etype.toLowerCase() === 'haplotype' || ent.name.includes('*');
              return (
                <div key={ent.canonical_id} className="understood-chip" role="listitem">
                  <span className={`chip-name ${isAllele ? 'font-mono' : ''}`}>
                    {ent.candidates?.[0]?.display_name || ent.name}
                  </span>
                  <span className="chip-cid font-mono">{ent.canonical_id}</span>
                  <span className="chip-type-badge">{etype}</span>
                  {ent.resolved_via && (
                    <span className="chip-via-pill">
                      {ent.resolved_via === 'hint' ? 'via selection' : 'via text'}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 3. Showing mode label and explanation */}
      <div className="results-mode-row">
        <span className="results-row-label">Showing:</span>
        <div className="results-mode-content">
          <span className={`results-mode-badge ${modeInfo.badgeClass}`}>
            {modeInfo.label}
          </span>
          <span className="results-mode-explanation">{modeInfo.explanation}</span>
        </div>
      </div>

      {/* 4. Try next suggestions */}
      {suggestedNext && suggestedNext.length > 0 && (
        <div className="results-try-next-row">
          <span className="results-row-label">Try next:</span>
          <div className="try-next-pills" role="list">
            {suggestedNext.map((item, idx) => (
              <button
                key={idx}
                type="button"
                className="btn-try-next-pill"
                onClick={() => onSelectSuggestion(item.label, item.entity_ids)}
              >
                <span>{item.label}</span>
                <span className="pill-arrow" aria-hidden="true">&rarr;</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </header>
  );
};

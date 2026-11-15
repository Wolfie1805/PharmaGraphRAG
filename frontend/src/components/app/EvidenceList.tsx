import React, { useState } from 'react';
import { EvidenceItem } from '../../types';

interface EvidenceListProps {
  items: EvidenceItem[];
  highlightedSourceId?: string | null;
}

type FilterType = 'all' | 'guideline' | 'drug_label' | 'annotation' | 'pubmed';

export const EvidenceList: React.FC<EvidenceListProps> = ({
  items = [],
  highlightedSourceId,
}) => {
  const [activeFilter, setActiveFilter] = useState<FilterType>('all');
  const [expandedProvenance, setExpandedProvenance] = useState<Record<string, boolean>>({});

  const toggleProvenance = (id: string) => {
    setExpandedProvenance((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const getSourceBadge = (item: EvidenceItem): { label: string; badgeClass: string } => {
    const prov = item.provenance || {};
    const srcName = (prov.source_name as string) || '';
    if (item.source_type === 'guideline') {
      return { label: srcName ? `CPIC / ${srcName}` : 'CPIC Guideline', badgeClass: 'badge-guideline' };
    }
    if (item.source_type === 'drug_label') {
      return { label: srcName ? `ClinPGx / ${srcName}` : 'Drug Label (ClinPGx)', badgeClass: 'badge-label' };
    }
    if (item.source_type === 'annotation') {
      return { label: 'PharmGKB Annotation', badgeClass: 'badge-annotation' };
    }
    if (item.source_type === 'pubmed') {
      return { label: 'PubMed Literature', badgeClass: 'badge-pubmed' };
    }
    return { label: item.source_type, badgeClass: 'badge-default' };
  };

  const filteredItems = items.filter((item) => {
    if (activeFilter === 'all') return true;
    return item.source_type === activeFilter;
  });

  const filterTabs: { id: FilterType; label: string; count: number }[] = [
    { id: 'all', label: 'All Evidence', count: items.length },
    { id: 'guideline', label: 'Guidelines', count: items.filter((i) => i.source_type === 'guideline').length },
    { id: 'drug_label', label: 'Drug Labels', count: items.filter((i) => i.source_type === 'drug_label').length },
    { id: 'annotation', label: 'Annotations', count: items.filter((i) => i.source_type === 'annotation').length },
    { id: 'pubmed', label: 'Literature', count: items.filter((i) => i.source_type === 'pubmed').length },
  ];

  return (
    <div className="evidence-list-section" aria-label="Curated Evidence Items">
      <div className="evidence-list-header">
        <h3 className="evidence-list-title">Retrieved Evidence Documents</h3>
        <span className="evidence-count-badge">
          Showing {filteredItems.length} of {items.length} items
        </span>
      </div>

      {/* Source Type Filter Tabs */}
      <div className="evidence-filter-bar" role="tablist" aria-label="Filter evidence by source type">
        {filterTabs.map((tab) => {
          const isSelected = activeFilter === tab.id;
          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={isSelected}
              className={`evidence-filter-pill ${isSelected ? 'is-active' : ''}`}
              onClick={() => setActiveFilter(tab.id)}
              type="button"
            >
              {tab.label} <span className="tab-pill-count">({tab.count})</span>
            </button>
          );
        })}
      </div>

      {/* Cards List */}
      <div className="evidence-cards-container">
        {filteredItems.map((item, index) => {
          const badge = getSourceBadge(item);
          const isHighlighted = highlightedSourceId === item.source_id;
          const isProvOpen = !!expandedProvenance[item.source_id];
          const prov = item.provenance || {};

          // Extract metadata
          const pmid = (prov.pmid as string) || (item.source_type === 'pubmed' ? item.source_id : undefined);
          const isNumericPmid = !!(pmid && /^\d+$/.test(pmid.trim()));
          const recLevel = (prov.recommendation_level as string) || (prov.guideline_level as string);
          const pgxLevel = (prov.pgx_level as string) || (prov.level_of_evidence as string);
          const year = item.date ? (item.date.match(/\b(19\d\d|20\d\d)\b/) || [])[0] : undefined;

          // Match types
          const matchTypes: string[] = [];
          if (item.retrieval_paths && item.retrieval_paths.length > 0) {
            matchTypes.push(...item.retrieval_paths);
          }
          if (prov.linked_via_relationship_pmid) {
            matchTypes.push('linked paper');
          }

          return (
            <article
              key={`${item.source_id}-${index}`}
              id={`evidence-${item.source_id}`}
              className={`evidence-card ${isHighlighted ? 'is-highlighted card-highlighted' : ''}`}
              aria-label={`Evidence card from ${badge.label}`}
            >
              {/* Card Header: Source badge + Title */}
              <div className="card-top-row">
                <span className={`source-type-pill ${badge.badgeClass}`}>
                  {badge.label}
                </span>
                <span className="source-id-mono">ID: {item.source_id}</span>
              </div>

              <h4 className="evidence-card-title">{item.title || item.source_id}</h4>

              {/* Quote Excerpt */}
              <blockquote className="evidence-quote-box">
                <span className="quote-mark">“</span>
                <span className="quote-text">{item.chunk_text}</span>
                <span className="quote-mark">”</span>
              </blockquote>

              {/* Metadata Row */}
              <div className="evidence-metadata-row">
                {isNumericPmid && pmid ? (
                  <span className="meta-item meta-pmid">
                    PubMed:{' '}
                    <a
                      href={`https://pubmed.ncbi.nlm.nih.gov/${pmid.trim()}/`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="pmid-link"
                    >
                      {pmid.trim()} ↗
                    </a>
                  </span>
                ) : pmid ? (
                  <span className="meta-item meta-pmid">PMID: {pmid}</span>
                ) : null}

                {recLevel && (
                  <span className="meta-item meta-rec-level">
                    Rec Level: <strong>{recLevel}</strong>
                  </span>
                )}

                {pgxLevel && (
                  <span className="meta-item meta-pgx-level">
                    PGx Level: <strong>{pgxLevel}</strong>
                  </span>
                )}

                {year && (
                  <span className="meta-item meta-year">
                    Year: <strong>{year}</strong>
                  </span>
                )}
              </div>

              {/* Collapsible Provenance */}
              <div className="provenance-section">
                <button
                  type="button"
                  className="provenance-toggle-btn"
                  onClick={() => toggleProvenance(item.source_id)}
                  aria-expanded={isProvOpen}
                >
                  <span className="toggle-arrow">{isProvOpen ? '▼' : '▶'}</span>
                  <span>{isProvOpen ? 'Hide provenance' : 'View provenance'}</span>
                </button>

                {isProvOpen && (
                  <div className="provenance-details-panel">
                    <div className="prov-row">
                      <span className="prov-label">Canonical ID:</span>
                      <span className="prov-val-mono">
                        {(prov.canonical_id as string) || (prov.chunk_id as string) || item.source_id}
                      </span>
                    </div>
                    <div className="prov-row">
                      <span className="prov-label">Retrieval Rank:</span>
                      <span className="prov-val-mono">#{index + 1}</span>
                    </div>
                    {matchTypes.length > 0 && (
                      <div className="prov-row">
                        <span className="prov-label">Match Types:</span>
                        <div className="prov-tags-row">
                          {matchTypes.map((mt, mtIdx) => (
                            <span key={`${mt}-${mtIdx}`} className="match-type-tag">
                              {mt}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {item.score !== undefined && (
                      <div className="prov-row">
                        <span className="prov-label">Fusion Score:</span>
                        <span className="prov-val-mono">{item.score.toFixed(4)}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
};

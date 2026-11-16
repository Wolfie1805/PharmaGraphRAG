import React, { useState } from 'react';
import { Claim, DetailSections, EvidenceItem, VariantFindingGroup, VariantFindingItem } from '../../types';

interface DetailSectionsViewProps {
  sections: DetailSections;
  claims: Claim[];
  answer: string;
  highlightedSourceId?: string | null;
  onCitationClick?: (sourceId: string) => void;
}

export const DetailSectionsView: React.FC<DetailSectionsViewProps> = ({
  sections,
  claims = [],
  answer,
  highlightedSourceId,
  onCitationClick,
}) => {
  // Collapsible state for variant groups (default all open)
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {};
    (sections.variant_findings || []).forEach((g) => {
      init[g.variant_tag] = true;
    });
    return init;
  });

  const toggleGroup = (tag: string) => {
    setOpenGroups((prev) => ({
      ...prev,
      [tag]: !prev[tag],
    }));
  };

  const guidelines = sections.guidelines || [];
  const drugLabels = sections.drug_labels || [];
  const variantFindings = sections.variant_findings || [];
  const linkedPapers = sections.linked_papers || [];
  const recordedRels = sections.recorded_relationships || [];

  return (
    <div className="detail-sections-view" aria-label="Detailed Evidence Sections">
      {/* 0. At A Glance Summary */}
      {answer && (
        <section className="detail-glance-card" aria-label="At a glance summary">
          <div className="glance-card-header">
            <span className="glance-label">At a glance</span>
            <span className="glance-badge">Extractive Synthesis</span>
          </div>
          <p className="glance-answer-text">{answer}</p>
          {claims.length > 0 && (
            <div className="glance-claims-list">
              <span className="claims-list-title">Verified Claims:</span>
              <ul className="claims-ul">
                {claims.map((claim, idx) => (
                  <li key={idx} className="claim-item">
                    <span className="claim-text">{claim.text}</span>
                    <span className="claim-sources">
                      {claim.source_ids.map((sid) => (
                        <button
                          key={sid}
                          type="button"
                          className="claim-citation-btn font-mono"
                          onClick={() => onCitationClick?.(sid)}
                          aria-label={`Citation ${sid}`}
                        >
                          [{sid}]
                        </button>
                      ))}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {/* 1. Clinical Guidelines */}
      <section className="evidence-section" id="section-guidelines" aria-labelledby="heading-guidelines">
        <div className="section-header-row">
          <h3 id="heading-guidelines" className="section-title">
            1. Clinical Guidelines (CPIC / DPWG)
          </h3>
          <span className="section-count-badge">{guidelines.length}</span>
        </div>
        {guidelines.length === 0 ? (
          <div className="section-empty-card">
            No clinical guidelines cataloged for this query in the current archive.
          </div>
        ) : (
          <div className="section-items-list" role="list">
            {guidelines.map((item: EvidenceItem) => {
              const isHighlighted = highlightedSourceId === item.source_id;
              return (
                <article
                  key={item.source_id}
                  id={`evidence-${item.source_id}`}
                  className={`evidence-record-card ${isHighlighted ? 'highlighted-record card-highlighted' : ''}`}
                  role="listitem"
                >
                  <div className="record-top-row">
                    <span className="record-source-id font-mono">ID: {item.source_id}</span>
                    <span className="record-type-badge badge-guideline">Guideline</span>
                  </div>
                  <h4 className="record-title">{item.title}</h4>
                  <p className="record-sentence">{item.chunk_text}</p>
                </article>
              );
            })}
          </div>
        )}
      </section>

      {/* 2. Drug Label Annotations */}
      <section className="evidence-section" id="section-drug-labels" aria-labelledby="heading-drug-labels">
        <div className="section-header-row">
          <h3 id="heading-drug-labels" className="section-title">
            2. Drug Label Annotations (FDA, EMA, PMDA, HCSC)
          </h3>
          <span className="section-count-badge">{drugLabels.length}</span>
        </div>
        {drugLabels.length === 0 ? (
          <div className="section-empty-card">
            No regulatory drug label annotations recorded for this pair.
          </div>
        ) : (
          <div className="section-items-list" role="list">
            {drugLabels.map((item: EvidenceItem) => {
              const isHighlighted = highlightedSourceId === item.source_id;
              return (
                <article
                  key={item.source_id}
                  id={`evidence-${item.source_id}`}
                  className={`evidence-record-card ${isHighlighted ? 'highlighted-record card-highlighted' : ''}`}
                  role="listitem"
                >
                  <div className="record-top-row">
                    <span className="record-source-id font-mono">ID: {item.source_id}</span>
                    <span className="record-type-badge badge-drug-label">Drug Label</span>
                  </div>
                  <h4 className="record-title">{item.title}</h4>
                  <p className="record-sentence">{item.chunk_text}</p>
                </article>
              );
            })}
          </div>
        )}
      </section>

      {/* 3. Variant-Level Clinical Findings */}
      <section className="evidence-section" id="section-variant-findings" aria-labelledby="heading-variant-findings">
        <div className="section-header-row">
          <h3 id="heading-variant-findings" className="section-title">
            3. Variant-Level Clinical Findings
          </h3>
          <span className="section-count-badge">
            {variantFindings.reduce((acc, g) => acc + g.findings.length, 0)} findings in {variantFindings.length} groups
          </span>
        </div>
        {variantFindings.length === 0 ? (
          <div className="section-empty-card">
            No variant-level clinical findings cataloged for this entity pair.
          </div>
        ) : (
          <div className="variant-groups-list">
            {variantFindings.map((group: VariantFindingGroup) => {
              const isOpen = openGroups[group.variant_tag] !== false;
              const isStarAllele = group.variant_tag.includes('*');
              return (
                <div key={group.variant_tag} className="variant-group-card">
                  <button
                    type="button"
                    className="variant-group-header-btn"
                    onClick={() => toggleGroup(group.variant_tag)}
                    aria-expanded={isOpen}
                  >
                    <div className="group-header-left">
                      <span className={`group-tag ${isStarAllele ? 'font-mono' : ''}`}>
                        {group.variant_tag}
                      </span>
                      <span className="group-count-badge">
                        {group.findings.length} {group.findings.length === 1 ? 'finding' : 'findings'}
                      </span>
                    </div>
                    <span className="group-toggle-arrow" aria-hidden="true">
                      {isOpen ? '▲' : '▼'}
                    </span>
                  </button>

                  {isOpen && (
                    <div className="variant-findings-list" role="list">
                      {group.findings.map((finding: VariantFindingItem) => {
                        const isHighlighted = highlightedSourceId === finding.source_id;
                        return (
                          <article
                            key={finding.source_id}
                            id={`evidence-${finding.source_id}`}
                            className={`finding-item-card ${isHighlighted ? 'highlighted-record' : ''}`}
                            role="listitem"
                          >
                            <div className="finding-top-row">
                              <span className="finding-id font-mono">Annotation {finding.source_id}</span>
                              {finding.pmid && (
                                <a
                                  href={`https://pubmed.ncbi.nlm.nih.gov/${finding.pmid}/`}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="finding-pmid-link font-mono"
                                  aria-label={`View PMID ${finding.pmid} on PubMed`}
                                >
                                  <span>PMID {finding.pmid}</span>
                                  <span className="ext-icon" aria-hidden="true">&#x2197;</span>
                                </a>
                              )}
                            </div>

                            <p className="finding-sentence">{finding.sentence}</p>

                            {/* Structured Columns Badges */}
                            <div className="finding-badges-row">
                              {finding.significance && (
                                <div className="structured-badge">
                                  <span className="badge-col-label">{finding.source_columns?.significance || 'Significance'}:</span>
                                  <span className="badge-col-value">{finding.significance}</span>
                                </div>
                              )}
                              {finding.phenotype_category && (
                                <div className="structured-badge">
                                  <span className="badge-col-label">{finding.source_columns?.phenotype_category || 'Phenotype Category'}:</span>
                                  <span className="badge-col-value">{finding.phenotype_category}</span>
                                </div>
                              )}
                              {finding.direction_of_effect && (
                                <div className="structured-badge">
                                  <span className="badge-col-label">{finding.source_columns?.direction_of_effect || 'Direction of effect'}:</span>
                                  <span className="badge-col-value">{finding.direction_of_effect}</span>
                                </div>
                              )}
                              {finding.population_types && (
                                <div className="structured-badge">
                                  <span className="badge-col-label">{finding.source_columns?.population_types || 'Population types'}:</span>
                                  <span className="badge-col-value">{finding.population_types}</span>
                                </div>
                              )}
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* 4. Papers Cited */}
      <section className="evidence-section" id="section-papers" aria-labelledby="heading-papers">
        <div className="section-header-row">
          <h3 id="heading-papers" className="section-title">
            4. Papers Cited
          </h3>
          <span className="section-count-badge">{linkedPapers.length}</span>
        </div>
        {linkedPapers.length === 0 ? (
          <div className="section-empty-card">
            No primary PubMed literature records cited for this query.
          </div>
        ) : (
          <div className="section-items-list" role="list">
            {linkedPapers.map((item: EvidenceItem) => {
              const pmidClean = item.source_id.replace(/^pmid:/i, '');
              const isHighlighted = highlightedSourceId === item.source_id;
              return (
                <article
                  key={item.source_id}
                  id={`evidence-${item.source_id}`}
                  className={`evidence-record-card ${isHighlighted ? 'highlighted-record card-highlighted' : ''}`}
                  role="listitem"
                >
                  <div className="record-top-row">
                    <span className="record-source-id font-mono">PMID: {pmidClean}</span>
                    <a
                      href={`https://pubmed.ncbi.nlm.nih.gov/${pmidClean}/`}
                      target="_blank"
                      rel="noreferrer"
                      className="pubmed-ext-link font-mono"
                      aria-label={`Open PubMed article ${pmidClean} in a new tab`}
                    >
                      <span>PubMed</span>
                      <span className="ext-icon" aria-hidden="true">&#x2197;</span>
                    </a>
                  </div>
                  <h4 className="record-title">{item.title}</h4>
                  <p className="record-sentence">{item.chunk_text}</p>
                </article>
              );
            })}
          </div>
        )}
      </section>

      {/* 5. Recorded Relationships */}
      <section className="evidence-section" id="section-recorded-relationships" aria-labelledby="heading-recorded-relationships">
        <div className="section-header-row">
          <h3 id="heading-recorded-relationships" className="section-title">
            5. Recorded Relationships
          </h3>
          <span className="section-count-badge">{recordedRels.length}</span>
        </div>
        {recordedRels.length === 0 ? (
          <div className="section-empty-card">
            No relationship graph edges recorded for this pair.
          </div>
        ) : (
          <div className="section-items-list" role="list">
            {recordedRels.map((item: EvidenceItem) => {
              const isHighlighted = highlightedSourceId === item.source_id;
              return (
                <article
                  key={item.source_id}
                  id={`evidence-${item.source_id}`}
                  className={`evidence-record-card ${isHighlighted ? 'highlighted-record card-highlighted' : ''}`}
                  role="listitem"
                >
                  <div className="record-top-row">
                    <span className="record-source-id font-mono">Record: {item.source_id}</span>
                    <span className="record-type-badge badge-rel">Relationship</span>
                  </div>
                  <h4 className="record-title">{item.title}</h4>
                  <p className="record-sentence">{item.chunk_text}</p>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
};

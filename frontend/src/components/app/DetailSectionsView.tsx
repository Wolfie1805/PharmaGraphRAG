import React, { useEffect, useMemo, useState } from 'react';
import { Claim, DetailSections, EvidenceItem, VariantFindingGroup, VariantFindingItem } from '../../types';

interface DetailSectionsViewProps {
  sections: DetailSections;
  claims: Claim[];
  answer: string;
  highlightedSourceId?: string | null;
  onCitationClick?: (sourceId: string) => void;
}

type SectionKey = 'guidelines' | 'drug_labels' | 'variant_findings' | 'papers' | 'relationships';

const ASSOC_HELP_NOTE =
  'This is the value stored in the source record. It is not a judgement by this tool and is unrelated to name ambiguity.';

export const DetailSectionsView: React.FC<DetailSectionsViewProps> = ({
  sections,
  claims = [],
  answer,
  highlightedSourceId,
  onCitationClick,
}) => {
  const guidelines = useMemo(() => sections.guidelines || [], [sections.guidelines]);
  const drugLabels = useMemo(() => sections.drug_labels || [], [sections.drug_labels]);
  const variantFindings = useMemo(
    () => sections.variant_findings || [],
    [sections.variant_findings]
  );
  const linkedPapers = useMemo(() => sections.linked_papers || [], [sections.linked_papers]);
  const allLinkedPapers = useMemo(
    () => sections.all_linked_papers || [],
    [sections.all_linked_papers]
  );
  const recordedRels = useMemo(
    () => sections.recorded_relationships || [],
    [sections.recorded_relationships]
  );

  const totalVariantFindings = variantFindings.reduce((acc, g) => acc + g.findings.length, 0);

  // Section disclosure state: guidelines OPEN by default; all other sections COLLAPSED
  const [openSections, setOpenSections] = useState<Record<SectionKey, boolean>>({
    guidelines: true,
    drug_labels: false,
    variant_findings: false,
    papers: false,
    relationships: false,
  });

  // Variant group disclosure state: first 3 groups OPEN by default, beyond 3 COLLAPSED
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {};
    variantFindings.forEach((g, idx) => {
      init[g.variant_tag] = idx < 3;
    });
    return init;
  });

  const [showAllPapers, setShowAllPapers] = useState(false);
  const [papersPage, setPapersPage] = useState(1);
  const PAPERS_PER_PAGE = 5;
  const pagedAllPapers = allLinkedPapers.slice(0, papersPage * PAPERS_PER_PAGE);

  // If a citation is clicked, automatically expand the section/group containing it
  useEffect(() => {
    if (!highlightedSourceId) return;
    if (guidelines.some((it) => it.source_id === highlightedSourceId)) {
      setOpenSections((prev) => ({ ...prev, guidelines: true }));
    } else if (drugLabels.some((it) => it.source_id === highlightedSourceId)) {
      setOpenSections((prev) => ({ ...prev, drug_labels: true }));
    } else if (linkedPapers.some((it) => it.source_id === highlightedSourceId)) {
      setOpenSections((prev) => ({ ...prev, papers: true }));
    } else if (recordedRels.some((it) => it.source_id === highlightedSourceId)) {
      setOpenSections((prev) => ({ ...prev, relationships: true }));
    } else {
      const matchingGroup = variantFindings.find((g) =>
        g.findings.some((f) => f.source_id === highlightedSourceId)
      );
      if (matchingGroup) {
        setOpenSections((prev) => ({ ...prev, variant_findings: true }));
        setOpenGroups((prev) => ({ ...prev, [matchingGroup.variant_tag]: true }));
      }
    }
    const timer = window.setTimeout(() => {
      const target = document.getElementById(`evidence-${highlightedSourceId}`);
      if (target && typeof target.scrollIntoView === 'function') {
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [highlightedSourceId, guidelines, drugLabels, linkedPapers, recordedRels, variantFindings]);

  const toggleSection = (key: SectionKey) => {
    setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleGroup = (tag: string) => {
    setOpenGroups((prev) => ({
      ...prev,
      [tag]: !prev[tag],
    }));
  };

  const jumpToSection = (key: SectionKey, elementId: string) => {
    setOpenSections((prev) => ({ ...prev, [key]: true }));
    const el = document.getElementById(elementId);
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

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

      {/* Section Jump Links Bar */}
      <nav className="section-jump-bar" aria-label="Evidence section jump links">
        <button
          type="button"
          className="section-jump-btn"
          onClick={() => jumpToSection('guidelines', 'section-guidelines')}
        >
          Guideline annotations ({guidelines.length})
        </button>
        <button
          type="button"
          className="section-jump-btn"
          onClick={() => jumpToSection('drug_labels', 'section-drug-labels')}
        >
          Drug labels ({drugLabels.length})
        </button>
        <button
          type="button"
          className="section-jump-btn"
          onClick={() => jumpToSection('variant_findings', 'section-variant-findings')}
        >
          Variant findings ({totalVariantFindings})
        </button>
        <button
          type="button"
          className="section-jump-btn"
          onClick={() => jumpToSection('papers', 'section-papers')}
        >
          Papers cited ({linkedPapers.length})
        </button>
        <button
          type="button"
          className="section-jump-btn"
          onClick={() => jumpToSection('relationships', 'section-recorded-relationships')}
        >
          Recorded relationships ({recordedRels.length})
        </button>
      </nav>

      {/* 1. Guideline annotations (ClinPGx) — OPEN by default */}
      <section className="evidence-section" id="section-guidelines" aria-labelledby="heading-guidelines">
        <div className="section-header-row">
          <button
            type="button"
            className="section-collapse-btn"
            onClick={() => toggleSection('guidelines')}
            aria-expanded={openSections.guidelines}
            aria-controls="section-guidelines-body"
          >
            <div className="section-title-group">
              <h3 id="heading-guidelines" className="section-title">
                1. Guideline annotations (ClinPGx) ({guidelines.length})
              </h3>
              {sections.guidelines_label && (
                <span className="section-subtitle-pill">{sections.guidelines_label}</span>
              )}
            </div>
            <span className="section-toggle-indicator" aria-hidden="true">
              {openSections.guidelines ? '▲' : '▼'}
            </span>
          </button>
        </div>
        {openSections.guidelines && (
          <div id="section-guidelines-body">
            {guidelines.length === 0 ? (
              <div className="section-empty-card">
                No guideline annotations cataloged for this query in the current archive.
              </div>
            ) : (
              <div className="section-items-list" role="list">
                {guidelines.map((item: EvidenceItem) => {
                  const isHighlighted = highlightedSourceId === item.source_id;
                  const issuingBody =
                    typeof item.provenance?.['guideline.source'] === 'string' &&
                    item.provenance['guideline.source'].trim().length > 0
                      ? item.provenance['guideline.source'].trim()
                      : null;
                  return (
                    <article
                      key={item.source_id}
                      id={`evidence-${item.source_id}`}
                      className={`evidence-record-card ${isHighlighted ? 'highlighted-record card-highlighted' : ''}`}
                      role="listitem"
                    >
                      <div className="record-top-row">
                        <span className="record-source-id font-mono">ID: {item.source_id}</span>
                        <div className="record-badges-right">
                          {issuingBody && (
                            <span className="guideline-source-badge font-mono">
                              guideline.source: {issuingBody}
                            </span>
                          )}
                          <span className="record-type-badge badge-guideline">Guideline</span>
                        </div>
                      </div>
                      <h4 className="record-title">{item.title}</h4>
                      <p className="record-sentence">{item.chunk_text}</p>
                    </article>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </section>

      {/* 2. Drug Label Annotations — COLLAPSED by default */}
      <section className="evidence-section" id="section-drug-labels" aria-labelledby="heading-drug-labels">
        <div className="section-header-row">
          <button
            type="button"
            className="section-collapse-btn"
            onClick={() => toggleSection('drug_labels')}
            aria-expanded={openSections.drug_labels}
            aria-controls="section-drug-labels-body"
          >
            <div className="section-title-group">
              <h3 id="heading-drug-labels" className="section-title">
                2. Drug Label Annotations (from ClinPGx) ({drugLabels.length})
              </h3>
              {sections.drug_labels_label && (
                <span className="section-subtitle-pill">{sections.drug_labels_label}</span>
              )}
            </div>
            <span className="section-toggle-indicator" aria-hidden="true">
              {openSections.drug_labels ? '▲' : '▼'}
            </span>
          </button>
        </div>
        {openSections.drug_labels && (
          <div id="section-drug-labels-body">
            {drugLabels.length === 0 ? (
              <div className="section-empty-card">
                No drug label annotations from ClinPGx recorded for this pair.
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
          </div>
        )}
      </section>

      {/* 3. Variant-Level Clinical Findings — COLLAPSED by default; groups beyond first 3 collapsed */}
      <section className="evidence-section" id="section-variant-findings" aria-labelledby="heading-variant-findings">
        <div className="section-header-row">
          <button
            type="button"
            className="section-collapse-btn"
            onClick={() => toggleSection('variant_findings')}
            aria-expanded={openSections.variant_findings}
            aria-controls="section-variant-findings-body"
          >
            <div className="section-title-group">
              <h3 id="heading-variant-findings" className="section-title">
                3. Variant-Level Clinical Findings ({totalVariantFindings} findings in {variantFindings.length} groups)
              </h3>
            </div>
            <span className="section-toggle-indicator" aria-hidden="true">
              {openSections.variant_findings ? '▲' : '▼'}
            </span>
          </button>
        </div>
        {openSections.variant_findings && (
          <div id="section-variant-findings-body">
            {variantFindings.length === 0 ? (
              <div className="section-empty-card">
                No variant-level clinical findings cataloged for this entity pair.
              </div>
            ) : (
              <div className="variant-groups-list">
                {variantFindings.map((group: VariantFindingGroup, idx: number) => {
                  const isOpen = openGroups[group.variant_tag] ?? idx < 3;
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
                                <div className="finding-structured-meta">
                                  {finding.significance && (
                                    <span
                                      className={`meta-badge meta-sig-${finding.significance.toLowerCase()}`}
                                      title={`Raw column: ${finding.source_columns?.significance || 'Significance'}`}
                                    >
                                      <span className="meta-col-name">
                                        {finding.source_columns?.significance || 'Significance'}:
                                      </span>{' '}
                                      {finding.significance}
                                    </span>
                                  )}
                                  {finding.phenotype_category && (
                                    <span
                                      className="meta-badge meta-pheno"
                                      title={`Raw column: ${finding.source_columns?.phenotype_category || 'Phenotype Category'}`}
                                    >
                                      <span className="meta-col-name">
                                        {finding.source_columns?.phenotype_category || 'Phenotype Category'}:
                                      </span>{' '}
                                      {finding.phenotype_category}
                                    </span>
                                  )}
                                  {finding.direction_of_effect && (
                                    <span
                                      className="meta-badge meta-dir"
                                      title={`Raw column: ${finding.source_columns?.direction_of_effect || 'Direction of effect'}`}
                                    >
                                      <span className="meta-col-name">
                                        {finding.source_columns?.direction_of_effect || 'Direction of effect'}:
                                      </span>{' '}
                                      {finding.direction_of_effect}
                                    </span>
                                  )}
                                  {finding.population_types && (
                                    <span
                                      className="meta-badge meta-pop"
                                      title={`Raw column: ${finding.source_columns?.population_types || 'Population types'}`}
                                    >
                                      <span className="meta-col-name">
                                        {finding.source_columns?.population_types || 'Population types'}:
                                      </span>{' '}
                                      {finding.population_types}
                                    </span>
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
          </div>
        )}
      </section>

      {/* 4. Papers Cited — COLLAPSED by default */}
      <section className="evidence-section" id="section-papers" aria-labelledby="heading-papers">
        <div className="section-header-row">
          <button
            type="button"
            className="section-collapse-btn"
            onClick={() => toggleSection('papers')}
            aria-expanded={openSections.papers}
            aria-controls="section-papers-body"
          >
            <div className="section-title-group">
              <h3 id="heading-papers" className="section-title">
                4. Papers Cited ({linkedPapers.length})
              </h3>
            </div>
            <span className="section-toggle-indicator" aria-hidden="true">
              {openSections.papers ? '▲' : '▼'}
            </span>
          </button>
        </div>
        {openSections.papers && (
          <div id="section-papers-body">
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

            {/* Paged "Show all linked papers" list (relationship PMIDs present in the corpus) */}
            {allLinkedPapers.length > 0 && (
              <div className="all-linked-papers-container">
                <div className="all-papers-toggle-row">
                  <button
                    type="button"
                    className="btn-toggle-all-papers"
                    onClick={() => setShowAllPapers(!showAllPapers)}
                    aria-expanded={showAllPapers}
                  >
                    {showAllPapers
                      ? 'Hide all linked papers'
                      : `Show all linked papers (${allLinkedPapers.length} in corpus)`}
                  </button>
                  <span className="all-papers-note">
                    Relationship PMIDs present in corpus
                  </span>
                </div>

                {showAllPapers && (
                  <div className="all-papers-paged-list">
                    <div className="section-items-list" role="list">
                      {pagedAllPapers.map((item: EvidenceItem) => {
                        const pmidClean = item.source_id.replace(/^pmid:/i, '');
                        return (
                          <article
                            key={item.source_id}
                            className="evidence-record-card all-paper-item"
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
                          </article>
                        );
                      })}
                    </div>

                    {pagedAllPapers.length < allLinkedPapers.length && (
                      <div className="all-papers-pagination-row">
                        <button
                          type="button"
                          className="btn-show-more-papers"
                          onClick={() => setPapersPage((p) => p + 1)}
                        >
                          Show more linked papers ({pagedAllPapers.length} of {allLinkedPapers.length})
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </section>

      {/* 5. Recorded Relationships — COLLAPSED by default */}
      <section className="evidence-section" id="section-recorded-relationships" aria-labelledby="heading-recorded-relationships">
        <div className="section-header-row">
          <button
            type="button"
            className="section-collapse-btn"
            onClick={() => toggleSection('relationships')}
            aria-expanded={openSections.relationships}
            aria-controls="section-relationships-body"
          >
            <div className="section-title-group">
              <h3 id="heading-recorded-relationships" className="section-title">
                5. Recorded Relationships ({recordedRels.length})
              </h3>
            </div>
            <span className="section-toggle-indicator" aria-hidden="true">
              {openSections.relationships ? '▲' : '▼'}
            </span>
          </button>
        </div>
        {openSections.relationships && (
          <div id="section-relationships-body">
            {recordedRels.length === 0 ? (
              <div className="section-empty-card">
                No relationship graph edges recorded for this pair.
              </div>
            ) : (
              <div className="section-items-list" role="list">
                {recordedRels.map((item: EvidenceItem) => {
                  const isHighlighted = highlightedSourceId === item.source_id;
                  const statedAssociation =
                    typeof item.provenance?.association === 'string'
                      ? item.provenance.association
                      : typeof item.graph_edges?.[0]?.association === 'string'
                      ? String(item.graph_edges[0].association)
                      : null;
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
                      {statedAssociation && (
                        <div className="rel-assoc-block">
                          <span className="assoc-pill assoc-ambiguous">
                            ClinPGx relationship record states: {statedAssociation}
                          </span>
                          <p className="assoc-help-note">{ASSOC_HELP_NOTE}</p>
                        </div>
                      )}
                      <h4 className="record-title">{item.title}</h4>
                      <p className="record-sentence">{item.chunk_text}</p>
                    </article>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
};

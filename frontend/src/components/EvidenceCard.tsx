import React, { useState } from 'react';
import { EvidenceItem } from '../types';

interface EvidenceCardProps {
  item: EvidenceItem;
  isHighlighted: boolean;
}

export const EvidenceCard: React.FC<EvidenceCardProps> = ({ item, isHighlighted }) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [showAllPmids, setShowAllPmids] = useState<boolean>(false);

  const isNumericPmid = (id: string): boolean => {
    return /^\d+$/.test(id.trim());
  };

  const sourceTypeLower = item.source_type.toLowerCase();
  const isRelRecord = sourceTypeLower === 'relationship_record';
  const isAnnotation = sourceTypeLower === 'annotation' || sourceTypeLower.includes('annotation');
  const isPubMedSource = sourceTypeLower === 'pubmed' || sourceTypeLower === 'publication';

  const semicolonPmids =
    isPubMedSource && item.source_id.includes(';')
      ? item.source_id
          .split(';')
          .map((p) => p.trim())
          .filter((p) => isNumericPmid(p))
      : [];

  const statedAssociation =
    typeof item.provenance?.association === 'string'
      ? item.provenance.association
      : typeof item.graph_edges?.[0]?.association === 'string'
      ? String(item.graph_edges[0].association)
      : null;

  const dateDisplay =
    item.date &&
    item.date !== 'unknown' &&
    item.date !== 'unspecified' &&
    item.date.toLowerCase() !== 'no date in data'
      ? item.date
      : 'No date in data';

  const isLongExcerpt = item.chunk_text.length > 220;
  const displayedExcerpt =
    isLongExcerpt && !isExpanded
      ? item.chunk_text.slice(0, 220) + '...'
      : item.chunk_text;

  const displayedTitle =
    semicolonPmids.length > 0 && item.title.length > 90
      ? `Supporting Publications (${semicolonPmids.length} PMIDs)`
      : item.title;

  const visiblePmids = showAllPmids ? semicolonPmids : semicolonPmids.slice(0, 4);

  return (
    <article
      id={`evidence-${item.source_id}`}
      className={`evidence-card ${isHighlighted ? 'card-highlighted' : ''}`}
      aria-labelledby={`evidence-title-${item.source_id}`}
    >
      <div className="card-header">
        <span className={`source-type-badge source-${sourceTypeLower}`}>
          {item.source_type}
        </span>

        <div className="card-source-id">
          {isRelRecord ? (
            <span className="source-id-text">
              <strong>Association (as stated by source)</strong>
              {statedAssociation ? `: ${statedAssociation}` : ''} | Record ID: {item.source_id}
            </span>
          ) : isAnnotation ? (
            <span className="source-id-text">
              <strong>Annotation ID:</strong> {item.source_id}
            </span>
          ) : isPubMedSource && isNumericPmid(item.source_id) ? (
            <a
              href={`https://pubmed.ncbi.nlm.nih.gov/${item.source_id}/`}
              target="_blank"
              rel="noopener noreferrer"
              className="pubmed-link"
              title="Open PubMed article in new tab"
            >
              PMID: {item.source_id} &#x2197;
            </a>
          ) : semicolonPmids.length > 0 ? (
            <span className="pmid-link-list">
              {visiblePmids.map((pmid, i) => (
                <React.Fragment key={pmid}>
                  {i > 0 ? ', ' : ''}
                  <a
                    href={`https://pubmed.ncbi.nlm.nih.gov/${pmid}/`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="pubmed-link"
                    title={`Open PMID ${pmid} on PubMed in new tab`}
                  >
                    PMID: {pmid} &#x2197;
                  </a>
                </React.Fragment>
              ))}
              {semicolonPmids.length > 4 && (
                <button
                  type="button"
                  className="toggle-pmids-btn"
                  onClick={() => setShowAllPmids(!showAllPmids)}
                >
                  {showAllPmids ? 'Show fewer PMIDs' : `+${semicolonPmids.length - 4} more`}
                </button>
              )}
            </span>
          ) : (
            <span className="source-id-text">ID: {item.source_id}</span>
          )}
        </div>

        <span className="evidence-date">
          Date: {dateDisplay}
        </span>
      </div>

      <h4 id={`evidence-title-${item.source_id}`} className="evidence-title">
        {displayedTitle}
      </h4>

      <div className="evidence-excerpt">
        {/* Render chunk text strictly as a plain React text node */}
        <p className="excerpt-text">{displayedExcerpt}</p>
        {isLongExcerpt && (
          <button
            type="button"
            className="toggle-excerpt-btn"
            onClick={() => setIsExpanded(!isExpanded)}
            aria-expanded={isExpanded}
          >
            {isExpanded ? 'Show less' : 'Show full excerpt'}
          </button>
        )}
      </div>

      <div className="card-footer">
        {item.matched_entities && item.matched_entities.length > 0 && (
          <div className="matched-entities">
            <span className="meta-label">Matched entities:</span>
            {item.matched_entities.map((m) => (
              <span key={m} className="matched-tag">
                {m}
              </span>
            ))}
          </div>
        )}

        <div className="retrieval-paths">
          <span className="meta-label">Paths:</span>
          {item.retrieval_paths.map((p) => (
            <span key={p} className="path-tag">
              {p}
            </span>
          ))}
        </div>

        <div className="score-badge">
          RRF Score: {item.score.toFixed(4)}
        </div>
      </div>
    </article>
  );
};

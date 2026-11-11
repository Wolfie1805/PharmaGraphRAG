import React from 'react';
import { EvidenceBundle } from '../types';
import { EvidenceCard } from './EvidenceCard';

interface EvidencePanelProps {
  bundle: EvidenceBundle;
  highlightedSourceId: string | null;
}

export const EvidencePanel: React.FC<EvidencePanelProps> = ({
  bundle,
  highlightedSourceId,
}) => {
  if (!bundle || !bundle.items || bundle.items.length === 0) {
    return (
      <section className="evidence-panel empty-panel" aria-label="Retrieved Evidence">
        <h3>Retrieved Evidence</h3>
        <p className="no-evidence-text">No evidence items were retrieved for this query.</p>
      </section>
    );
  }

  // Check for old evidence: any dated item older than 10 years (e.g. before 2016)
  const hasOldEvidence = bundle.items.some((it) => {
    if (!it.date || it.date === 'unknown' || it.date === 'unspecified') return false;
    const yearMatch = it.date.match(/(\d{4})/);
    if (!yearMatch) return false;
    const year = parseInt(yearMatch[1], 10);
    return year > 1900 && year < 2016;
  });

  return (
    <section className="evidence-panel" aria-label="Retrieved Evidence Bundle">
      <div className="evidence-header">
        <div className="evidence-title-group">
          <h3>Retrieved Evidence Bundle</h3>
          <span className="total-items-badge">{bundle.total_items} items</span>
        </div>

        <div className="evidence-badges">
          {bundle.conflicts_detected && (
            <span className="badge badge-conflict" role="status">
              Conflicts Detected
            </span>
          )}
          {!bundle.has_sufficient_evidence && (
            <span className="badge badge-insufficient" role="status">
              Insufficient Evidence Threshold
            </span>
          )}
          {hasOldEvidence && (
            <span className="badge badge-old" role="status">
              Contains Historical Evidence (&lt; 2016)
            </span>
          )}
        </div>
      </div>

      <div className="cards-grid">
        {bundle.items.map((item, idx) => (
          <EvidenceCard
            key={`${item.source_id}-${idx}`}
            item={item}
            isHighlighted={highlightedSourceId === item.source_id}
          />
        ))}
      </div>
    </section>
  );
};

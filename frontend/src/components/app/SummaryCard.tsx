import React from 'react';
import { Claim } from '../../types';

interface SummaryCardProps {
  answer: string;
  claims: Claim[];
  flags: string[];
  answerMode?: string;
  onCitationClick?: (sourceId: string) => void;
}

export const SummaryCard: React.FC<SummaryCardProps> = ({
  answer,
  claims = [],
  flags = [],
  answerMode,
  onCitationClick,
}) => {
  // Collect all unique source IDs cited in claims
  const allSourceIds = Array.from(new Set(claims.flatMap((c) => c.source_ids)));

  // Derive assertion type badge
  const determineAssertion = (): { label: string; kind: string } => {
    const lowerAnswer = answer.toLowerCase();
    const joinedFlags = flags.join(' ').toLowerCase();

    if (joinedFlags.includes('contraindicated') || lowerAnswer.includes('contraindicated')) {
      return { label: 'Contraindicated', kind: 'contraindicated' };
    }
    if (joinedFlags.includes('actionable') || lowerAnswer.includes('actionable')) {
      return { label: 'Actionable Guidance', kind: 'actionable' };
    }
    if (joinedFlags.includes('inform') || lowerAnswer.includes('informational')) {
      return { label: 'Informational', kind: 'inform' };
    }
    if (joinedFlags.includes('not-actionable') || lowerAnswer.includes('not actionable')) {
      return { label: 'Not Actionable', kind: 'not-actionable' };
    }
    if (joinedFlags.includes('no-guidance') || lowerAnswer.includes('no specific guidance') || lowerAnswer.includes('insufficient')) {
      return { label: 'No Guidance Found', kind: 'no-guidance' };
    }
    return { label: 'Curated Extraction', kind: 'inform' };
  };

  const assertion = determineAssertion();

  return (
    <div className="summary-card" aria-label="Extractive Evidence Summary">
      <div className="summary-card-header">
        <h3 className="summary-card-title">
          Evidence summary (quoted from sources, no AI model)
        </h3>
        {answerMode && (
          <span className="summary-mode-tag">
            Mode: {answerMode}
          </span>
        )}
      </div>

      {/* Answer content rendered strictly as plain React text node */}
      <div className="summary-card-content">
        <p className="summary-text-body">{answer}</p>
      </div>

      {/* Claim and Assertion Badges */}
      <div className="summary-badges-footer">
        <div className="assertion-badge-group">
          <span className="badge-label">Clinical Assertion:</span>
          <span className={`assertion-pill pill-${assertion.kind}`}>
            {assertion.label}
          </span>
        </div>

        <div className="sources-badge-group">
          <span className="badge-label">Grounded Sources:</span>
          <span className="sources-count-pill">
            {allSourceIds.length} cited source{allSourceIds.length === 1 ? '' : 's'}
          </span>
        </div>

        {allSourceIds.length > 0 && onCitationClick && (
          <div className="cited-source-chips">
            {allSourceIds.map((sid) => (
              <button
                key={sid}
                type="button"
                className="cited-source-link-chip"
                onClick={() => onCitationClick(sid)}
                title={`Jump to evidence ${sid}`}
                aria-label={`Citation ${sid}`}
              >
                [{sid}]
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

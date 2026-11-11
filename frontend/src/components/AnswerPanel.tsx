import React from 'react';
import { Claim } from '../types';

interface AnswerPanelProps {
  answer: string;
  claims: Claim[];
  answerMode: string;
  flags: string[];
  removedClaimsCount: number;
  onCitationClick: (sourceId: string) => void;
}

function escapeRegExp(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function formatCitationLabel(sid: string): string {
  if (!sid.includes(';')) {
    return `[${sid}]`;
  }
  const parts = sid
    .split(';')
    .map((p) => p.trim())
    .filter(Boolean);
  if (parts.length <= 3) {
    return `[${parts.join(', ')}]`;
  }
  return `[${parts.slice(0, 3).join(', ')} (+${parts.length - 3} PMIDs)]`;
}

/**
 * Splits plain text into React text nodes and clickable citation buttons
 * for any known source ID appearing inside square brackets or exact citation tokens.
 * Never parses HTML or Markdown — asterisks such as *2/*3 remain literal text.
 */
function renderPlainAnswerWithCitations(
  text: string,
  knownSourceIds: string[],
  onCitationClick: (sourceId: string) => void
): React.ReactNode {
  if (!knownSourceIds.length || !text) {
    return text;
  }

  // Sort longest IDs first to avoid partial prefix matching
  const sortedIds = [...new Set(knownSourceIds)].sort((a, b) => b.length - a.length);
  const pattern = new RegExp(`(${sortedIds.map(escapeRegExp).join('|')})`, 'g');
  const idSet = new Set(sortedIds);

  const parts = text.split(pattern);
  return parts.map((part, idx) => {
    if (idSet.has(part)) {
      return (
        <button
          key={`inline-cit-${idx}-${part}`}
          type="button"
          className="inline-citation-pill"
          onClick={() => onCitationClick(part)}
          title={`Scroll to evidence card for ${part}`}
          aria-label={`Jump to evidence ${part}`}
        >
          {part}
        </button>
      );
    }
    return <React.Fragment key={`txt-${idx}`}>{part}</React.Fragment>;
  });
}

export const AnswerPanel: React.FC<AnswerPanelProps> = ({
  answer,
  claims,
  answerMode,
  flags,
  removedClaimsCount,
  onCitationClick,
}) => {
  const getModeLabel = (mode: string) => {
    switch (mode.toLowerCase()) {
      case 'extractive':
        return 'Extractive answer (no AI model)';
      case 'ollama':
        return 'Local Model (Ollama)';
      case 'mock':
        return 'Mock Test Adapter';
      default:
        return mode;
    }
  };

  const allSourceIds = claims.flatMap((c) => c.source_ids);

  return (
    <section className="answer-panel" aria-label="Synthesized Answer">
      <div className="answer-header">
        <div className="answer-mode-indicator">
          <span className="mode-badge" role="status">
            {getModeLabel(answerMode)}
          </span>
          {flags.includes('model_fallback') && (
            <span className="badge-fallback">Fallback to Extractive</span>
          )}
        </div>

        {removedClaimsCount > 0 && (
          <span className="badge-removed-claims" role="status">
            Verifier removed {removedClaimsCount} ungrounded claim(s)
          </span>
        )}
      </div>

      <div className="answer-body">
        <h3 className="section-heading">Synthesized Response</h3>
        {/* Render answer strictly as plain React text nodes + native buttons (never dangerouslySetInnerHTML or markdown) */}
        <p className="answer-narrative">
          {renderPlainAnswerWithCitations(answer, allSourceIds, onCitationClick)}
        </p>
      </div>

      {claims && claims.length > 0 && (
        <div className="claims-section">
          <h4 className="claims-heading">Verified Grounded Claims ({claims.length})</h4>
          <ol className="claims-list">
            {claims.map((claim, idx) => (
              <li key={`claim-${idx}`} className="claim-item">
                <span className="claim-text">{claim.text}</span>
                <div className="citation-markers">
                  <span className="citations-label">Sources:</span>
                  {claim.source_ids.map((sid) => (
                    <button
                      key={sid}
                      type="button"
                      className="citation-pill"
                      onClick={() => onCitationClick(sid)}
                      title={`Jump to evidence card for ${sid.includes(';') ? 'supporting PMID list' : sid}`}
                      aria-label={`Citation ${sid}`}
                    >
                      {formatCitationLabel(sid)}
                    </button>
                  ))}
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
};

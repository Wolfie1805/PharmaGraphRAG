import React from 'react';
import { Claim } from '../types';

interface AnswerPanelProps {
  answer: string;
  claims: Claim[];
  relatedClaims?: Claim[];
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

function splitAnswerAndLimitations(rawAnswer: string): {
  narrative: string;
  limitations: string | null;
} {
  const marker = '\n\nLimitations: ';
  const idx = rawAnswer.indexOf(marker);
  if (idx === -1) {
    return { narrative: rawAnswer, limitations: null };
  }
  return {
    narrative: rawAnswer.slice(0, idx).trim(),
    limitations: rawAnswer.slice(idx + marker.length).trim(),
  };
}

export const AnswerPanel: React.FC<AnswerPanelProps> = ({
  answer,
  claims,
  relatedClaims = [],
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

  const allSourceIds = [...claims, ...relatedClaims].flatMap((c) => c.source_ids);
  const { narrative, limitations } = splitAnswerAndLimitations(answer);
  const isInsufficient = flags.includes('insufficient_evidence');

  return (
    <section className="answer-panel" aria-label="Extractive Evidence Summary">
      <div className="answer-header">
        <div className="answer-mode-indicator">
          <span className="mode-badge" role="status">
            {getModeLabel(answerMode)}
          </span>
          {flags.includes('model_fallback') && (
            <span className="badge-fallback">Fallback to Extractive</span>
          )}
        </div>

        <span className="badge-removed-claims" role="status">
          Removed ungrounded claims: {removedClaimsCount}
        </span>
      </div>

      {isInsufficient && (
        <div className="insufficient-banner" role="alert">
          <strong>Insufficient Evidence:</strong> Retrieved evidence did not meet minimum threshold requirements for an extractive summary.
        </div>
      )}

      <div className="answer-body">
        <h3 className="section-heading">Extractive Evidence Summary</h3>
        {/* Render answer strictly as plain React text nodes + native buttons (never dangerouslySetInnerHTML or markdown) */}
        <p className="answer-narrative">
          {renderPlainAnswerWithCitations(narrative, allSourceIds, onCitationClick)}
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

      {relatedClaims && relatedClaims.length > 0 && (
        <div className="related-claims-section">
          <h4 className="claims-heading">
            Related evidence (matches only one queried entity) ({relatedClaims.length})
          </h4>
          <ol className="claims-list">
            {relatedClaims.map((claim, idx) => (
              <li key={`related-claim-${idx}`} className="claim-item">
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
                      aria-label={`Related citation ${sid}`}
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

      {limitations && (
        <div className="limitations-box">
          <h4 className="limitations-heading">Limitations</h4>
          <p className="limitations-text">{limitations}</p>
        </div>
      )}

      <div className="answer-audit-footer" aria-label="Response Audit Metadata">
        <div className="audit-flags">
          <span className="audit-label">Flags:</span>
          {flags.length > 0 ? (
            flags.map((flag) => (
              <span key={flag} className="audit-flag-tag">
                {flag}
              </span>
            ))
          ) : (
            <span className="audit-flag-neutral">none</span>
          )}
        </div>
        <div className="audit-removed">
          <span className="audit-label">Verifier removed claims:</span>{' '}
          <strong className="audit-removed-count">{removedClaimsCount}</strong>
        </div>
      </div>
    </section>
  );
};

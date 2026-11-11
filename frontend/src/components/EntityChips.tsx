import React, { useState, useEffect } from 'react';
import { ResolvedEntity, EntityCandidate } from '../types';

interface EntityChipsProps {
  entities: ResolvedEntity[];
  onSelectCandidate: (candidateName: string, originalQuery?: string) => void;
}

export const EntityChips: React.FC<EntityChipsProps> = ({ entities, onSelectCandidate }) => {
  const [activeModalEntity, setActiveModalEntity] = useState<ResolvedEntity | null>(null);

  useEffect(() => {
    if (!activeModalEntity) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setActiveModalEntity(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeModalEntity]);

  if (!entities || entities.length === 0) {
    return null;
  }

  return (
    <div className="entity-chips-container" aria-label="Resolved entities">
      <span className="chips-label">Detected Entities:</span>
      <div className="chips-list">
        {entities.map((entity, idx) => {
          const isAmbiguous = entity.status === 'ambiguous';
          return (
            <div
              key={`${entity.query}-${idx}`}
              className={`entity-chip ${isAmbiguous ? 'chip-ambiguous' : 'chip-resolved'}`}
            >
              <span className="chip-name">{entity.query}</span>
              {entity.canonical_id && (
                <span className="chip-id">({entity.canonical_id})</span>
              )}
              {isAmbiguous ? (
                <button
                  type="button"
                  className="ambiguity-btn"
                  onClick={() => setActiveModalEntity(entity)}
                  aria-label={`Resolve ambiguous entity ${entity.query}`}
                >
                  Ambiguous (Pick candidate)
                </button>
              ) : (
                <span className="chip-status-badge">{entity.status === 'resolved' ? 'Resolved' : entity.status}</span>
              )}
            </div>
          );
        })}
      </div>

      {activeModalEntity && (
        <div
          className="modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setActiveModalEntity(null);
            }
          }}
        >
          <div className="modal-content">
            <h3 id="modal-title">Disambiguate Entity: &ldquo;{activeModalEntity.query}&rdquo;</h3>
            <p className="modal-desc">
              Multiple biomedical concepts match this term. Please choose one to refine and re-run your query:
            </p>
            <ul className="candidate-list">
              {(activeModalEntity.candidates || []).map((candidate: EntityCandidate) => (
                <li key={candidate.canonical_id} className="candidate-item">
                  <button
                    type="button"
                    className="candidate-choice-btn"
                    onClick={() => {
                      const originalQuery = activeModalEntity.query;
                      setActiveModalEntity(null);
                      onSelectCandidate(candidate.display_name, originalQuery);
                    }}
                  >
                    <span className="candidate-name">{candidate.display_name}</span>
                    <span className="candidate-meta">
                      Type: {candidate.entity_type} | ID: {candidate.canonical_id} | Defined by: {candidate.defined_by}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            <div className="modal-actions">
              <button
                type="button"
                className="btn-cancel"
                onClick={() => setActiveModalEntity(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

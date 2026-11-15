import React from 'react';
import { EvidenceBundle, ResolvedEntity } from '../../types';

interface AtAGlanceCardProps {
  resolvedEntities: ResolvedEntity[];
  evidenceBundle: EvidenceBundle;
}

export const AtAGlanceCard: React.FC<AtAGlanceCardProps> = ({
  resolvedEntities,
  evidenceBundle,
}) => {
  // Aggregate evidence counts by source type
  const items = evidenceBundle.items || [];
  const guidelinesCount = items.filter((i) => i.source_type === 'guideline').length;
  const drugLabelsCount = items.filter((i) => i.source_type === 'drug_label').length;
  const annotationsCount = items.filter((i) => i.source_type === 'annotation').length;
  const pubmedCount = items.filter((i) => i.source_type === 'pubmed').length;

  const countPills: { label: string; count: number }[] = [
    { label: 'guidelines', count: guidelinesCount },
    { label: 'drug labels', count: drugLabelsCount },
    { label: 'annotations', count: annotationsCount },
    { label: 'papers', count: pubmedCount },
  ].filter((p) => p.count > 0);

  const hasAmbiguous = resolvedEntities.some((e) => e.status === 'ambiguous');
  const hasUngrounded = resolvedEntities.some((e) => e.status === 'unresolved');

  return (
    <div className="at-a-glance-card" aria-label="Query Overview and Detected Entities">
      <div className="glance-header">
        <span className="glance-title">At a Glance</span>
        <div className="glance-badges">
          {hasAmbiguous && (
            <span className="warning-pill warning-ambiguous">
              Ambiguity detected
            </span>
          )}
          {hasUngrounded && (
            <span className="warning-pill warning-ungrounded">
              Ungrounded entity
            </span>
          )}
        </div>
      </div>

      {/* Detected Entities */}
      <div className="glance-entities-section">
        <span className="glance-subheading">Detected Entities:</span>
        <div className="glance-chips-row">
          {resolvedEntities.map((ent, idx) => {
            const via = ent.resolved_via || 'text';
            const typeLabel = ent.entity_type || (ent.candidate_types && ent.candidate_types[0]) || 'Entity';
            const isOverridden = !!ent.hint_overrode_text;

            return (
              <div
                key={`${ent.canonical_id || ent.name}-${idx}`}
                className={`entity-glance-chip status-${ent.status}`}
              >
                <span className="entity-chip-name">{ent.name || ent.query}</span>
                <span className="entity-chip-type">{typeLabel}</span>
                <span className={`entity-chip-via via-${via}`}>
                  via {via}
                </span>
                {isOverridden && (
                  <span className="entity-chip-override" title="User hint took precedence over text resolution">
                    hint override
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Evidence Counts */}
      <div className="glance-counts-section">
        <span className="glance-subheading">Evidence Counts:</span>
        <div className="glance-counts-row">
          {countPills.length > 0 ? (
            countPills.map((pill) => (
              <span key={pill.label} className="evidence-count-pill">
                <strong className="count-number">{pill.count}</strong> {pill.label}
              </span>
            ))
          ) : (
            <span className="evidence-count-pill empty-count">
              0 curated evidence items
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

import React from 'react';

export const DoesNotDoSection: React.FC = () => {
  return (
    <section id="boundaries" className="section-container" aria-labelledby="boundaries-heading">
      <span className="section-tag">System Scope</span>
      <h2 id="boundaries-heading" className="section-heading">
        WHAT IT DOES / WHAT IT DOES NOT DO
      </h2>
      <p className="section-lead">
        PharmaGraph is strictly an extractive evidence retrieval tool. It operates within
        well-defined scientific boundaries and does not provide clinical guidance.
      </p>

      <div className="does-not-grid">
        {/* What It Does */}
        <div className="spotlight-card does-card">
          <div className="card-title-badge" style={{ color: '#ffffff' }}>
            <svg
              className="icon-check"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
            WHAT IT DOES
          </div>

          <ul className="check-list">
            <li className="check-item">
              <span className="icon-check" aria-hidden="true">✓</span>
              <span>Finds published scientific evidence connecting genetic variants to drug responses.</span>
            </li>
            <li className="check-item">
              <span className="icon-check" aria-hidden="true">✓</span>
              <span>Quotes verified passages directly from published guidelines and drug label annotations.</span>
            </li>
            <li className="check-item">
              <span className="icon-check" aria-hidden="true">✓</span>
              <span>Traverses structured recorded relationships linking genes, variants, and chemicals.</span>
            </li>
            <li className="check-item">
              <span className="icon-check" aria-hidden="true">✓</span>
              <span>Returns deterministic citations with exact source provenance.</span>
            </li>
          </ul>
        </div>

        {/* What It Does NOT Do (Prominent) */}
        <div className="spotlight-card not-card" role="region" aria-label="System Limitations and Negations">
          <div className="card-title-badge" style={{ color: '#ef4444' }}>
            <svg
              className="icon-cross"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
            WHAT IT DOES NOT DO
          </div>

          <ul className="check-list">
            <li className="check-item negated">
              <span className="icon-cross" aria-hidden="true">✕</span>
              <span><strong>Does not diagnose:</strong> Never used to diagnose any medical condition or illness.</span>
            </li>
            <li className="check-item negated">
              <span className="icon-cross" aria-hidden="true">✕</span>
              <span><strong>Does not prescribe or dose:</strong> Does not prescribe drugs, calculate dosages, or adjust regimens.</span>
            </li>
            <li className="check-item negated">
              <span className="icon-cross" aria-hidden="true">✕</span>
              <span><strong>Does not treat or advise:</strong> Does not treat patients, recommend therapies, or provide personal medical advice.</span>
            </li>
            <li className="check-item negated">
              <span className="icon-cross" aria-hidden="true">✕</span>
              <span><strong>Does not read your DNA:</strong> Never accepts, uploads, or sequences patient DNA data.</span>
            </li>
            <li className="check-item negated">
              <span className="icon-cross" aria-hidden="true">✕</span>
              <span><strong>Does not know brand names:</strong> Resolves international non-proprietary chemical names only.</span>
            </li>
            <li className="check-item negated">
              <span className="icon-cross" aria-hidden="true">✕</span>
              <span><strong>No full paper text:</strong> Indexes curated abstracts and excerpts, not paywalled full articles.</span>
            </li>
            <li className="check-item negated">
              <span className="icon-cross" aria-hidden="true">✕</span>
              <span><strong>No medicine uses or side effects:</strong> Excludes general therapeutic uses or non-pharmacogenomic adverse effects.</span>
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
};

export default DoesNotDoSection;

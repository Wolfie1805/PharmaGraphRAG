import React from 'react';

export const UseCasesSection: React.FC = () => {
  return (
    <section id="use-cases" className="section-container" aria-labelledby="use-cases-heading">
      <span className="section-tag">Intended Applications</span>
      <h2 id="use-cases-heading" className="section-heading">
        WHERE IT CAN BE USED
      </h2>
      <p className="section-lead">
        Designed to assist academic researchers, educators, and informed patients exploring
        pharmacogenomic literature.
      </p>

      <div className="use-cases-grid">
        <div className="use-case-list">
          <div className="spotlight-card use-case-card">
            <div className="use-case-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </div>
            <div>
              <h3 className="benefit-title" style={{ marginBottom: '0.35rem' }}>
                Research Literature Scouting
              </h3>
              <p className="benefit-desc">
                Rapidly identify published gene-variant-drug associations across drug labels, CPIC guidelines,
                and PubMed abstracts with exact provenance.
              </p>
            </div>
          </div>

          <div className="spotlight-card use-case-card">
            <div className="use-case-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
              </svg>
            </div>
            <div>
              <h3 className="benefit-title" style={{ marginBottom: '0.35rem' }}>
                Education and Mechanism Study
              </h3>
              <p className="benefit-desc">
                Learn how functional polymorphisms impact drug-metabolizing enzymes, transport proteins,
                and therapeutic pathways.
              </p>
            </div>
          </div>

          <div className="spotlight-card use-case-card">
            <div className="use-case-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <div>
              <h3 className="benefit-title" style={{ marginBottom: '0.35rem' }}>
                Formulating Questions for Healthcare Providers
              </h3>
              <p className="benefit-desc">
                Prepare well-structured, evidence-backed questions to discuss with a licensed physician
                or clinical pharmacologist.
              </p>
            </div>
          </div>
        </div>

        {/* Explicit Non-Use Card */}
        <div
          className="spotlight-card"
          style={{
            background: '#161214',
            borderTop: '3px solid rgba(239, 68, 68, 0.6)',
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--font-body)',
              fontSize: '12px',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: '#ef4444',
              fontWeight: 600,
            }}
          >
            EXPLICITLY RESTRICTED
          </span>
          <h3 style={{ fontFamily: 'var(--font-heading)', color: '#ffffff', fontSize: '1.1rem', margin: 0 }}>
            NOT FOR CLINICAL OR PERSONAL MEDICAL USE
          </h3>
          <p style={{ fontSize: '0.88rem', color: '#9a9aa0', lineHeight: 1.5, margin: 0 }}>
            PharmaGraph is an experimental academic prototype. It is not an authorized medical device
            and must never be used in emergency care, bedside decision making, or direct patient care.
          </p>
        </div>
      </div>
    </section>
  );
};

export default UseCasesSection;

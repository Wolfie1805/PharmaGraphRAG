import React from 'react';

interface Benefit {
  title: string;
  desc: string;
  badge: string;
}

const BENEFITS: Benefit[] = [
  {
    title: 'Traceable to a source',
    badge: 'Provenance',
    desc: 'Every extracted claim links directly to a verified guideline ID, drug label accession, or PubMed PMID.',
  },
  {
    title: 'Nothing made up',
    badge: 'Extractive',
    desc: 'Passages are quoted verbatim from authoritative source documents. The system does not generate speculative text.',
  },
  {
    title: 'Runs locally',
    badge: 'Self-Contained',
    desc: 'The entire retrieval core, index tables, and compact bi-encoder embedding model run completely on your local workstation.',
  },
  {
    title: 'Free to run',
    badge: 'Zero Cloud Cost',
    desc: 'No external API keys, proprietary subscription tokens, or third-party cloud infrastructure required.',
  },
  {
    title: 'Repeatable results',
    badge: 'Deterministic',
    desc: 'Reciprocal rank fusion and deterministic tie-breaking guarantee that identical queries return identical results.',
  },
  {
    title: 'Honest about gaps',
    badge: 'Transparent',
    desc: 'Unindexed source types and missing associations are explicitly reported rather than masked.',
  },
];

export const BenefitsSection: React.FC = () => {
  return (
    <section id="benefits" className="section-container" aria-labelledby="benefits-heading">
      <span className="section-tag">Core Advantages</span>
      <h2 id="benefits-heading" className="section-heading">
        KEY SYSTEM BENEFITS
      </h2>
      <p className="section-lead">
        Engineered for rigorous scientific verification, complete offline autonomy, and absolute
        traceability.
      </p>

      <div className="benefits-grid">
        {BENEFITS.map((b) => (
          <div key={b.title} className="spotlight-card benefit-card">
            <span
              style={{
                fontFamily: 'var(--font-body)',
                fontSize: '12px',
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: '#e5e5e8',
                border: '1px solid var(--lp-border)',
                borderRadius: '4px',
                padding: '0.2rem 0.5rem',
                alignSelf: 'flex-start',
              }}
            >
              {b.badge}
            </span>
            <h3 className="benefit-title">{b.title}</h3>
            <p className="benefit-desc">{b.desc}</p>
          </div>
        ))}
      </div>
    </section>
  );
};

export default BenefitsSection;

import React, { useState } from 'react';

interface StepInfo {
  num: number;
  title: string;
  desc: string;
  detail: string;
}

const STEPS: StepInfo[] = [
  {
    num: 1,
    title: 'Collect official data',
    desc: 'Collects curated ClinPGx files (annotations, drug label annotations and guideline annotations), CPIC allele definitions and PubMed abstracts.',
    detail: 'Data sources are fetched from authoritative public repositories without alteration.',
  },
  {
    num: 2,
    title: 'Keep originals untouched',
    desc: 'Raw source archives are preserved in their original format with cryptographically verified fingerprints.',
    detail: 'Every archive file is hashed with SHA-256 to ensure complete auditability.',
  },
  {
    num: 3,
    title: 'Clean and give each thing one ID',
    desc: 'Normalizes terms into unambiguous identifiers for genes, variants, haplotypes, and chemical entities.',
    detail: 'Resolves complex synonyms and star allele nomenclature into stable canonical IDs.',
  },
  {
    num: 4,
    title: 'Search several ways',
    desc: 'Executes four coordinated retrieval paths: keyword lexical search, local embeddings, graph traversal, and entity tags.',
    detail: 'Combines lexical precision with semantic vector search and curated graph relationships.',
  },
  {
    num: 5,
    title: 'Merge and rank',
    desc: 'Combines candidates using deterministic Reciprocal Rank Fusion with balanced source slot allocation.',
    detail: 'Guarantees balanced representation across guidelines, labels, and research papers.',
  },
  {
    num: 6,
    title: 'Show quoted evidence with sources',
    desc: 'Extracts verbatim quoted passages with persistent provenance links and citation integrity verification.',
    detail: 'Every sentence is checked to ensure no ungrounded claims are surfaced.',
  },
];

const renderStepIcon = (num: number) => {
  switch (num) {
    case 1:
      return (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="7 10 12 15 17 10" />
          <line x1="12" y1="15" x2="12" y2="3" />
        </svg>
      );
    case 2:
      return (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
      );
    case 3:
      return (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
          <line x1="7" y1="7" x2="7.01" y2="7" />
        </svg>
      );
    case 4:
      return (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
          <line x1="11" y1="8" x2="11" y2="14" />
          <line x1="8" y1="11" x2="14" y2="11" />
        </svg>
      );
    case 5:
      return (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <line x1="18" y1="20" x2="18" y2="10" />
          <line x1="12" y1="20" x2="12" y2="4" />
          <line x1="6" y1="20" x2="6" y2="14" />
        </svg>
      );
    case 6:
      return (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
          <polyline points="10 9 9 9 8 9" />
        </svg>
      );
    default:
      return null;
  }
};

export const HowItWorksSection: React.FC = () => {
  const [activeStep, setActiveStep] = useState<number>(1);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    let nextStep: number | null = null;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      nextStep = activeStep === 6 ? 1 : activeStep + 1;
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      nextStep = activeStep === 1 ? 6 : activeStep - 1;
    } else if (e.key === 'Home') {
      nextStep = 1;
    } else if (e.key === 'End') {
      nextStep = 6;
    }

    if (nextStep !== null) {
      e.preventDefault();
      setActiveStep(nextStep);
      const btn = document.getElementById(`step-tab-${nextStep}`);
      btn?.focus();
    }
  };

  return (
    <section id="how-it-works" className="section-container" aria-labelledby="how-it-works-heading">
      {/* Decorative thin curved background line */}
      <svg
        className="curved-bg-line"
        viewBox="0 0 1000 200"
        fill="none"
        style={{
          position: 'absolute',
          top: '20%',
          left: 0,
          width: '100%',
          height: 'auto',
          pointerEvents: 'none',
          opacity: 0.15,
          zIndex: 0,
        }}
        aria-hidden="true"
      >
        <path
          d="M0,100 C300,180 700,20 1000,100"
          stroke="rgba(255, 255, 255, 0.4)"
          strokeWidth="1.5"
          strokeDasharray="6 6"
        />
      </svg>

      <span className="section-tag">System Architecture</span>
      <h2 id="how-it-works-heading" className="section-heading">
        HOW IT WORKS
      </h2>
      <p className="section-lead">
        A repeatable six-step pipeline from official downloads to quoted evidence with sources.
      </p>

      {/* Interactive Tabs / Large Feature Showcase */}
      <div
        className="how-it-works-interactive"
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(240px, 1fr) 2fr',
          gap: '1.5rem',
          marginBottom: '2.5rem',
        }}
      >
        <div
          role="tablist"
          aria-label="Pipeline Steps"
          onKeyDown={handleKeyDown}
          style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}
        >
          {STEPS.map((s) => (
            <button
              key={s.num}
              role="tab"
              aria-selected={activeStep === s.num}
              aria-controls={`step-panel-${s.num}`}
              id={`step-tab-${s.num}`}
              onClick={() => setActiveStep(s.num)}
              style={{
                background: activeStep === s.num ? '#202023' : '#131314',
                color: activeStep === s.num ? '#ffffff' : '#9a9aa0',
                border: `1px solid ${activeStep === s.num ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.08)'}`,
                borderRadius: '8px',
                padding: '0.75rem 1rem',
                textAlign: 'left',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.85rem',
                transition: 'all 0.15s ease',
              }}
            >
              <span className="step-num-badge">{s.num}</span>
              <span style={{ fontWeight: 500, fontSize: '0.92rem' }}>{s.title}</span>
            </button>
          ))}
        </div>

        {STEPS.map((s) => (
          <div
            key={s.num}
            id={`step-panel-${s.num}`}
            role="tabpanel"
            aria-labelledby={`step-tab-${s.num}`}
            hidden={activeStep !== s.num}
            className="spotlight-card step-panel-container"
            style={{
              display: activeStep === s.num ? 'flex' : 'none',
            }}
          >
            <div className="step-panel-content">
              <span className="step-kicker-label">STEP {s.num}</span>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem',
                  marginBottom: '1rem',
                  color: '#ffffff',
                }}
              >
                <div
                  style={{
                    color: '#ffffff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'rgba(255, 255, 255, 0.06)',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    borderRadius: '8px',
                    width: '36px',
                    height: '36px',
                  }}
                >
                  {renderStepIcon(s.num)}
                </div>
                <h3 className="step-title" style={{ margin: 0, fontSize: '1.25rem' }}>
                  {s.title}
                </h3>
              </div>
              <p
                className="step-desc"
                style={{ fontSize: '1.05rem', color: '#f2f2f2', marginBottom: '1rem' }}
              >
                {s.desc}
              </p>
              <p style={{ fontSize: '0.9rem', color: '#9a9aa0', margin: 0, lineHeight: 1.6 }}>
                {s.detail}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* 6 Step Cards Grid */}
      <div className="flow-steps-grid">
        {STEPS.map((step) => (
          <div key={step.num} className="spotlight-card flow-step-card">
            <span className="step-kicker-label">STEP {step.num}</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div className="step-num-badge">{step.num}</div>
              <h3 className="step-title" style={{ margin: 0 }}>
                {step.title}
              </h3>
            </div>
            <p className="step-desc">{step.desc}</p>
          </div>
        ))}
      </div>
    </section>
  );
};

export default HowItWorksSection;

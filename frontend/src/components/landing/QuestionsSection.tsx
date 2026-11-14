import React, { useState } from 'react';

interface QuestionExample {
  title: string;
  query: string;
  entities: { gene: string; drug: string };
  description: string;
  highlight: string;
}

const QUESTIONS: QuestionExample[] = [
  {
    title: 'What is the relationship between CYP2C19 and clopidogrel?',
    query: 'What is the relationship between CYP2C19 and clopidogrel?',
    entities: { gene: 'CYP2C19', drug: 'clopidogrel' },
    description:
      'Surfaces guideline recommendations and drug label warnings regarding loss-of-function star alleles (*2, *3) and reduced antiplatelet activation.',
    highlight: 'Guidelines & Drug Labels',
  },
  {
    title: 'warfarin VKORC1',
    query: 'warfarin VKORC1',
    entities: { gene: 'VKORC1', drug: 'warfarin' },
    description:
      'Explores evidence linking promoter polymorphisms to altered vitamin K epoxide reductase subunit 1 expression and anticoagulant sensitivity.',
    highlight: 'Dosing Algorithms & Literature',
  },
  {
    title: 'Does SLCO1B1 matter for simvastatin?',
    query: 'Does SLCO1B1 matter for simvastatin?',
    entities: { gene: 'SLCO1B1', drug: 'simvastatin' },
    description:
      'Identifies clinical guidelines evaluating solute carrier organic anion transporter family member 1B1 variants associated with statin-induced myopathy risk.',
    highlight: 'Transporter PGx & Safety',
  },
];

export const QuestionsSection: React.FC = () => {
  const [currentIndex, setCurrentIndex] = useState<number>(0);

  const prevSlide = () => {
    if (currentIndex > 0) {
      setCurrentIndex((prev) => prev - 1);
    }
  };

  const nextSlide = () => {
    if (currentIndex < QUESTIONS.length - 1) {
      setCurrentIndex((prev) => prev + 1);
    }
  };

  return (
    <section id="example-questions" className="section-container" aria-labelledby="questions-heading">
      <span className="section-tag">Interactive Demonstrations</span>
      <h2 id="questions-heading" className="section-heading">
        QUESTIONS IT CAN ANSWER
      </h2>
      <p className="section-lead">
        Representative clinical pharmacogenomic queries illustrating multi-source evidence synthesis.
      </p>

      {/* Carousel Controls */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1rem',
        }}
      >
        <span style={{ fontSize: '0.85rem', color: '#9a9aa0', fontFamily: 'var(--font-mono)' }}>
          Query {currentIndex + 1} of {QUESTIONS.length}
        </span>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            type="button"
            onClick={prevSlide}
            disabled={currentIndex === 0}
            aria-label="Previous question"
            style={{
              background: '#1a1a1c',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: '#ffffff',
              borderRadius: '50%',
              width: '36px',
              height: '36px',
              cursor: currentIndex === 0 ? 'not-allowed' : 'pointer',
              opacity: currentIndex === 0 ? 0.3 : 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            ←
          </button>
          <button
            type="button"
            onClick={nextSlide}
            disabled={currentIndex === QUESTIONS.length - 1}
            aria-label="Next question"
            style={{
              background: '#1a1a1c',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: '#ffffff',
              borderRadius: '50%',
              width: '36px',
              height: '36px',
              cursor: currentIndex === QUESTIONS.length - 1 ? 'not-allowed' : 'pointer',
              opacity: currentIndex === QUESTIONS.length - 1 ? 0.3 : 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            →
          </button>
        </div>
      </div>

      {/* Cards Grid / Carousel View */}
      <div
        role="region"
        aria-roledescription="carousel"
        aria-label="Example pharmacogenomic queries"
        style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem' }}
      >
        {QUESTIONS.map((q, idx) => {
          const isFocused = idx === currentIndex;
          const appUrl = `#/app?q=${encodeURIComponent(q.query)}`;

          return (
            <div
              key={q.title}
              className="spotlight-card"
              style={{
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                borderColor: isFocused ? 'rgba(255, 255, 255, 0.3)' : undefined,
                boxShadow: isFocused
                  ? '0 0 0 1px rgba(255, 255, 255, 0.2), 0 0 24px rgba(255, 255, 255, 0.08)'
                  : undefined,
              }}
              role="group"
              aria-roledescription="slide"
              aria-label={`Example ${idx + 1}`}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <span
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.72rem',
                      letterSpacing: '0.08em',
                      textTransform: 'uppercase',
                      color: 'var(--lp-muted)',
                      border: '1px solid var(--lp-border)',
                      padding: '0.2rem 0.5rem',
                      borderRadius: '4px',
                    }}
                  >
                    {q.highlight}
                  </span>
                  <div style={{ display: 'flex', gap: '0.35rem' }}>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.72rem',
                        color: '#ffffff',
                        background: 'rgba(255,255,255,0.08)',
                        padding: '0.15rem 0.4rem',
                        borderRadius: '4px',
                      }}
                    >
                      {q.entities.gene}
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.72rem',
                        color: '#9a9aa0',
                        background: 'rgba(255,255,255,0.04)',
                        padding: '0.15rem 0.4rem',
                        borderRadius: '4px',
                      }}
                    >
                      {q.entities.drug}
                    </span>
                  </div>
                </div>

                <h3
                  style={{
                    fontFamily: 'var(--font-heading)',
                    fontSize: '1.15rem',
                    color: '#ffffff',
                    fontWeight: 400,
                    lineHeight: 1.4,
                    marginBottom: '0.85rem',
                  }}
                >
                  "{q.title}"
                </h3>

                <p style={{ fontSize: '0.88rem', color: '#9a9aa0', lineHeight: 1.5, marginBottom: '1.5rem' }}>
                  {q.description}
                </p>
              </div>

              <div>
                <a
                  href={appUrl}
                  className="btn-primary"
                  style={{
                    fontSize: '0.85rem',
                    padding: '0.5rem 1rem',
                    width: '100%',
                    justifyContent: 'center',
                    boxSizing: 'border-box',
                  }}
                >
                  Try this question →
                </a>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};

export default QuestionsSection;

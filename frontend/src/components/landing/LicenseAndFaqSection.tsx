import React, { useState } from 'react';
import { SiteStats } from '../../types';

interface LicenseAndFaqSectionProps {
  stats: SiteStats | null;
}

interface FAQItem {
  question: string;
  answer: string;
}

const FAQ_ITEMS: FAQItem[] = [
  {
    question: 'Why does this tool not diagnose illnesses or prescribe medications?',
    answer:
      'No. PharmaGraph does not diagnose any illness, does not prescribe any medication, and does not treat any medical condition. It is strictly an offline research prototype designed to index and quote published biomedical literature.',
  },
  {
    question: 'Where does the pharmacogenomic data come from?',
    answer:
      'Evidence is retrieved directly from published CPIC guidelines, drug label annotations from ClinPGx, curated annotations, and PubMed abstracts.',
  },
  {
    question: 'Does this tool transmit queries to external cloud servers?',
    answer:
      'No. The entire system executes on your local workstation. Queries, vector embeddings, and recorded relationship lookups remain completely offline. The data stays private.',
  },
  {
    question: 'Why does the tool refuse questions about patient dosages?',
    answer:
      'To prevent clinical harm, automated refusal gates intercept requests for dosing advice, patient therapy guidance, or personal recommendations.',
  },
  {
    question: 'What is the purpose of this software?',
    answer:
      'It is an informational tool for researchers and educators to discover and verify published gene-drug interaction evidence through transparent, traceable citations.',
  },
];

export const LicenseAndFaqSection: React.FC<LicenseAndFaqSectionProps> = ({ stats }) => {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  const toggleAccordion = (idx: number) => {
    setOpenIndex((prev) => (prev === idx ? null : idx));
  };

  const clinpgxSource = stats?.sources?.find((s) => s.name.toLowerCase().includes('clinpgx core'));

  return (
    <section id="faq" className="section-container" aria-labelledby="faq-heading">
      <span className="section-tag">Governance & FAQ</span>
      <h2 id="faq-heading" className="section-heading">
        DATA LICENSING & FAQ
      </h2>
      <p className="section-lead">
        Transparent terms of use, privacy assurances, and answers to common inquiries.
      </p>

      {/* Local Execution & Licensing Note Card */}
      <div className="spotlight-card" style={{ marginBottom: '2.5rem', borderLeft: '3px solid rgba(255, 255, 255, 0.4)' }}>
        <h3 style={{ fontFamily: 'var(--font-heading)', color: '#ffffff', fontSize: '1.15rem', marginBottom: '0.75rem' }}>
          LOCAL COMPUTATION & PRIVACY STATEMENT
        </h3>
        <p style={{ fontSize: '0.92rem', color: '#9a9aa0', lineHeight: 1.6, marginBottom: '1rem' }}>
          PharmaGraph runs locally without sending query telemetry or biometric data to remote endpoints.
          The data stays private.
        </p>

        <h4 style={{ fontFamily: 'var(--font-heading)', color: '#ffffff', fontSize: '1rem', marginBottom: '0.5rem' }}>
          CLINPGX LICENSE TERMS & WORKING ASSUMPTION
        </h4>
        <p style={{ fontSize: '0.88rem', color: '#9a9aa0', lineHeight: 1.5, marginBottom: '0.5rem' }}>
          ClinPGx-derived data carry license terms. For ClinPGx Core TSVs, a discrepancy is unresolved
          between the site footer license (CC BY-SA 4.0) and the archive bundled license (CC BY-NC-SA 4.0).
        </p>
        <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '0.85rem', borderRadius: '6px', fontSize: '0.82rem', border: '1px solid rgba(255,255,255,0.06)' }}>
          <p style={{ margin: '0 0 0.5rem 0', color: '#f59e0b', fontWeight: 500 }}>
            Discrepancy unresolved between site footer and bundled license.
          </p>
          <p style={{ margin: '0 0 0.5rem 0', color: '#e5e5e8' }}>
            Working assumption: NonCommercial reading until the owner decides.
          </p>
          {clinpgxSource?.license_notes && (
            <div style={{ marginTop: '0.5rem' }}>
              <span style={{ color: '#9a9aa0', fontWeight: 600 }}>Verbatim Quote: </span>
              <span style={{ color: '#ffffff', fontStyle: 'italic' }}>
                "{clinpgxSource.license_notes[1]?.quote ?? clinpgxSource.license_notes[0]?.quote}"
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Accessible FAQ Accordion */}
      <h3 style={{ fontFamily: 'var(--font-heading)', color: '#ffffff', fontSize: '1.25rem', marginBottom: '1.25rem' }}>
        FREQUENTLY ASKED QUESTIONS
      </h3>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '3.5rem' }} role="region" aria-label="FAQ Accordion">
        {FAQ_ITEMS.map((item, idx) => {
          const isOpen = openIndex === idx;
          const panelId = `faq-panel-${idx}`;
          const buttonId = `faq-btn-${idx}`;

          return (
            <div
              key={idx}
              className="spotlight-card"
              style={{
                padding: 0,
                overflow: 'hidden',
                borderColor: isOpen ? 'rgba(255, 255, 255, 0.2)' : undefined,
              }}
            >
              <button
                type="button"
                id={buttonId}
                aria-expanded={isOpen}
                aria-controls={panelId}
                onClick={() => toggleAccordion(idx)}
                style={{
                  width: '100%',
                  padding: '1.2rem 1.5rem',
                  background: 'transparent',
                  border: 'none',
                  color: '#ffffff',
                  textAlign: 'left',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  cursor: 'pointer',
                  fontFamily: 'var(--font-heading)',
                  fontSize: '1rem',
                  fontWeight: 400,
                }}
              >
                <span>{item.question}</span>
                <span
                  style={{
                    color: '#9a9aa0',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '1.1rem',
                    transform: isOpen ? 'rotate(45deg)' : 'rotate(0deg)',
                    transition: 'transform 0.15s ease',
                  }}
                  aria-hidden="true"
                >
                  +
                </span>
              </button>

              <div
                id={panelId}
                role="region"
                aria-labelledby={buttonId}
                hidden={!isOpen}
                style={{
                  display: isOpen ? 'block' : 'none',
                  padding: '0 1.5rem 1.25rem 1.5rem',
                  color: '#9a9aa0',
                  fontSize: '0.9rem',
                  lineHeight: 1.6,
                }}
              >
                {item.answer}
              </div>
            </div>
          );
        })}
      </div>

      {/* Call to Action Banner */}
      <div className="cta-banner">
        <h3 className="cta-title">EXPLORE THE PHARMACOGENOMICS EVIDENCE BASE</h3>
        <p style={{ color: '#9a9aa0', fontSize: '1rem', maxWidth: '600px', margin: '0 auto 2rem', lineHeight: 1.6 }}>
          Run offline inquiries across normalized guidelines, drug label annotations from ClinPGx, and scientific literature.
        </p>
        <a href="#/app" className="btn-primary" style={{ padding: '0.85rem 2.25rem', fontSize: '1rem' }}>
          Open the app →
        </a>
      </div>
    </section>
  );
};

export default LicenseAndFaqSection;

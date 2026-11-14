import React from 'react';
import { SiteStats } from '../../types';

interface QualitySectionProps {
  stats: SiteStats | null;
}

export const QualitySection: React.FC<QualitySectionProps> = ({ stats }) => {
  const bm = stats?.benchmark;

  return (
    <section id="quality" className="section-container" aria-labelledby="quality-heading">
      <span className="section-tag">Evaluation & Diagnostics</span>
      <h2 id="quality-heading" className="section-heading">
        MEASURED QUALITY
      </h2>
      <p className="section-lead">
        Automated regression metrics recorded during pipeline test runs.
      </p>

      {!bm ? (
        <div className="spotlight-card" style={{ textAlign: 'center', padding: '2.5rem' }}>
          <p style={{ color: '#9a9aa0', fontSize: '1.05rem', margin: 0 }}>Benchmark results pending</p>
        </div>
      ) : (
        <div className="spotlight-card" style={{ padding: '2rem' }}>
          {/* Diagnostic Label (Required exact wording) */}
          <div style={{ marginBottom: '1.25rem' }}>
            <span
              style={{
                fontFamily: 'var(--font-body)',
                fontSize: '12px',
                letterSpacing: '0.08em',
                color: '#e5e5e8',
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                padding: '0.35rem 0.85rem',
                borderRadius: '4px',
                display: 'inline-block',
                textTransform: 'uppercase',
              }}
            >
              Pipeline diagnostic, not a quality score, not human-verified
            </span>
          </div>

          <p style={{ fontSize: '0.9rem', color: '#9a9aa0', lineHeight: 1.6, marginBottom: '1.75rem' }}>
            These figures reflect automated regression checks run against synthetic validation pairs.
            They are technical sanity checks for code verification and do not indicate clinical efficacy.
          </p>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '1.25rem',
            }}
          >
            <div style={{ borderLeft: '2px solid rgba(255,255,255,0.1)', paddingLeft: '0.85rem' }}>
              <div style={{ fontSize: '0.75rem', color: '#9a9aa0', textTransform: 'uppercase' }}>
                Safety Guard Checks
              </div>
              <div style={{ fontSize: '1.25rem', fontFamily: 'var(--font-mono)', color: '#ffffff', marginTop: '0.2rem' }}>
                {bm.rule_checks?.guard ?? '—'}
              </div>
            </div>

            <div style={{ borderLeft: '2px solid rgba(255,255,255,0.1)', paddingLeft: '0.85rem' }}>
              <div style={{ fontSize: '0.75rem', color: '#9a9aa0', textTransform: 'uppercase' }}>
                Ambiguity Resolution Checks
              </div>
              <div style={{ fontSize: '1.25rem', fontFamily: 'var(--font-mono)', color: '#ffffff', marginTop: '0.2rem' }}>
                {bm.rule_checks?.ambiguity ?? '—'}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

export default QualitySection;

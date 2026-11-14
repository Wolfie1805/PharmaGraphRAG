import React from 'react';
import { SiteStats } from '../../types';

interface ReliabilitySectionProps {
  stats: SiteStats | null;
}

export const ReliabilitySection: React.FC<ReliabilitySectionProps> = ({ stats }) => {
  return (
    <section id="reliability" className="section-container" aria-labelledby="reliability-heading">
      <span className="section-tag">Verification & Trust</span>
      <h2 id="reliability-heading" className="section-heading">
        RELIABILITY & PROVENANCE
      </h2>
      <p className="section-lead">
        Deterministic validation mechanisms ensure scientific fidelity, verifiable citations,
        and strict refusal boundaries.
      </p>

      {/* Grid of Reliability Tenets */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '1.5rem',
          marginBottom: '2.5rem',
        }}
      >
        <div className="spotlight-card">
          <h3 className="benefit-title">Provenance on Every Record</h3>
          <p className="benefit-desc">
            Every candidate chunk preserves its immutable origin metadata: source repository,
            file release date, and original document section identifier.
          </p>
        </div>

        <div className="spotlight-card">
          <h3 className="benefit-title">Original files are stored with SHA-256 fingerprints in manifests</h3>
          <p className="benefit-desc">
            Raw downloads are saved untouched. Fingerprints are cryptographically verified to
            guarantee that ingested tables match upstream distributor releases.
          </p>
        </div>

        <div className="spotlight-card">
          <h3 className="benefit-title">Every Claim Cites a Source ID</h3>
          <p className="benefit-desc">
            Answers are strictly extractive. Statements returned carry direct
            citations linking to published guidelines, drug labels, or PMIDs.
          </p>
        </div>

        <div className="spotlight-card">
          <h3 className="benefit-title">Citation Checker Guard</h3>
          <p className="benefit-desc">
            An automated integrity checker verifies that candidate excerpts exist in the
            underlying index chunks, discarding unsupported claims.
          </p>
        </div>

        <div className="spotlight-card">
          <h3 className="benefit-title">Clinical Refusal Gates</h3>
          <p className="benefit-desc">
            Rule-based intent filters intercept requests attempting to solicit personal dosing
            calculations or diagnostic advice, returning safe educational explanations.
          </p>
        </div>

        <div className="spotlight-card">
          <h3 className="benefit-title">Repeatable Deterministic Output</h3>
          <p className="benefit-desc">
            Zero stochastic sampling during synthesis. Identical queries always generate
            identical candidate rankings and identical evidence order.
          </p>
        </div>
      </div>

      {/* Dynamic Test Verification Banner */}
      <div
        className="spotlight-card"
        style={{
          background: 'var(--lp-surface)',
          padding: '1.75rem',
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '1.5rem',
        }}
      >
        <div>
          <span
            style={{
              fontFamily: 'var(--font-body)',
              fontSize: '12px',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: '#e5e5e8',
            }}
          >
            REPOSITORY TEST SUITE
          </span>
          <h3 style={{ margin: '0.25rem 0 0 0', color: '#ffffff', fontSize: '1.15rem', fontFamily: 'var(--font-heading)' }}>
            AUTOMATED REGRESSION TEST SUITE
          </h3>
        </div>

        <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: '0.78rem', color: '#9a9aa0', textTransform: 'uppercase' }}>
              Backend Unit Tests
            </div>
            <div style={{ fontSize: '1.1rem', fontFamily: 'var(--font-mono)', color: '#ffffff', marginTop: '0.25rem' }}>
              {stats?.tests?.pytest_collected != null
                ? `${stats.tests.pytest_collected} automated tests are defined in the repository`
                : '—'}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.78rem', color: '#9a9aa0', textTransform: 'uppercase' }}>
              Frontend Specs
            </div>
            <div style={{ fontSize: '1.1rem', fontFamily: 'var(--font-mono)', color: '#ffffff', marginTop: '0.25rem' }}>
              {stats?.tests?.vitest_collected != null
                ? `${stats.tests.vitest_collected} automated tests are defined in the repository`
                : '—'}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default ReliabilitySection;

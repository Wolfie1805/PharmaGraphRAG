import React from 'react';
import { SiteStats } from '../../types';

interface SearchHonestySectionProps {
  stats: SiteStats | null;
}

export const SearchHonestySection: React.FC<SearchHonestySectionProps> = ({ stats }) => {
  const coverage = stats?.retrieval?.meaning_coverage;

  return (
    <section id="search-architecture" className="section-container" aria-labelledby="search-heading">
      <span className="section-tag">Search Architecture</span>
      <h2 id="search-heading" className="section-heading">
        HOW SEARCH WORKS, HONESTLY
      </h2>
      <p className="section-lead">
        Four parallel retrieval paths feed a reciprocal rank fusion engine. Vector semantic search
        is deliberately restricted to verified drug label and guideline corpora.
      </p>

      {/* Four Retrieval Paths */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '1.25rem',
          marginBottom: '2.5rem',
        }}
      >
        <div className="spotlight-card">
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: '#9a9aa0', marginBottom: '0.4rem' }}>
            PATH 1
          </div>
          <h3 className="benefit-title">Keyword Search</h3>
          <p className="benefit-desc">
            BM25 lexical scoring for exact gene nomenclature, star alleles, and international non-proprietary drug names.
          </p>
        </div>

        <div className="spotlight-card">
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: '#9a9aa0', marginBottom: '0.4rem' }}>
            PATH 2
          </div>
          <h3 className="benefit-title">Meaning Search</h3>
          <p className="benefit-desc">
            Local bi-encoder vector embeddings providing semantic similarity matching on compact local hardware.
          </p>
        </div>

        <div className="spotlight-card">
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: '#9a9aa0', marginBottom: '0.4rem' }}>
            PATH 3
          </div>
          <h3 className="benefit-title">Recorded Relationships</h3>
          <p className="benefit-desc">
            Deterministic graph traversal querying curated biological relationships between genes, variants, and chemicals.
          </p>
        </div>

        <div className="spotlight-card">
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: '#9a9aa0', marginBottom: '0.4rem' }}>
            PATH 4
          </div>
          <h3 className="benefit-title">Entity-Grounded Path</h3>
          <p className="benefit-desc">
            Structured metadata matching that prioritizes passages containing all resolved canonical entities.
          </p>
        </div>
      </div>

      {/* Meaning Search Honesty Table */}
      <div className="spotlight-card" style={{ marginBottom: '1.5rem', overflowX: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#ffffff', fontFamily: 'var(--font-heading)' }}>
            MEANING SEARCH COVERAGE BY SOURCE TYPE
          </h3>
          <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: '#9a9aa0' }}>
            Model: {stats?.retrieval?.embedding_model ?? 'Local Bi-Encoder'}
          </span>
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#9a9aa0' }}>
              <th style={{ padding: '0.6rem 0.75rem', fontWeight: 500 }}>Source Type</th>
              <th style={{ padding: '0.6rem 0.75rem', fontWeight: 500 }}>Meaning (Vector) Indexing</th>
              <th style={{ padding: '0.6rem 0.75rem', fontWeight: 500 }}>Keyword & Graph Paths</th>
              <th style={{ padding: '0.6rem 0.75rem', fontWeight: 500 }}>Coverage State</th>
            </tr>
          </thead>
          <tbody>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
              <td style={{ padding: '0.75rem', color: '#ffffff', fontWeight: 500 }}>Drug Labels (ClinPGx)</td>
              <td style={{ padding: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                {coverage?.drug_label
                  ? `${coverage.drug_label.indexed.toLocaleString()} / ${coverage.drug_label.expected.toLocaleString()} chunks`
                  : '—'}
              </td>
              <td style={{ padding: '0.75rem', color: '#9a9aa0' }}>Fully indexed</td>
              <td style={{ padding: '0.75rem' }}>
                <span style={{ color: '#10b981', fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}>
                  Covered
                </span>
              </td>
            </tr>

            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
              <td style={{ padding: '0.75rem', color: '#ffffff', fontWeight: 500 }}>Clinical Guidelines (CPIC)</td>
              <td style={{ padding: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                {coverage?.guideline
                  ? `${coverage.guideline.indexed.toLocaleString()} / ${coverage.guideline.expected.toLocaleString()} chunks`
                  : '—'}
              </td>
              <td style={{ padding: '0.75rem', color: '#9a9aa0' }}>Fully indexed</td>
              <td style={{ padding: '0.75rem' }}>
                <span style={{ color: '#10b981', fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}>
                  Covered
                </span>
              </td>
            </tr>

            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
              <td style={{ padding: '0.75rem', color: '#ffffff', fontWeight: 500 }}>Curated Annotations</td>
              <td style={{ padding: '0.75rem', fontFamily: 'var(--font-mono)', color: '#9a9aa0' }}>
                {coverage?.annotation
                  ? `${coverage.annotation.indexed.toLocaleString()} / ${coverage.annotation.expected.toLocaleString()} chunks`
                  : '—'}
              </td>
              <td style={{ padding: '0.75rem', color: '#ffffff' }}>Covered by keyword and graph search only</td>
              <td style={{ padding: '0.75rem' }}>
                <span style={{ color: '#9a9aa0', fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}>
                  Not in vector index
                </span>
              </td>
            </tr>

            <tr>
              <td style={{ padding: '0.75rem', color: '#ffffff', fontWeight: 500 }}>PubMed Research Papers</td>
              <td style={{ padding: '0.75rem', fontFamily: 'var(--font-mono)', color: '#9a9aa0' }}>
                {coverage?.pubmed
                  ? `${coverage.pubmed.indexed.toLocaleString()} / ${coverage.pubmed.expected.toLocaleString()} chunks`
                  : '—'}
              </td>
              <td style={{ padding: '0.75rem', color: '#ffffff' }}>Covered by keyword and graph search only</td>
              <td style={{ padding: '0.75rem' }}>
                <span style={{ color: '#9a9aa0', fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}>
                  Not in vector index
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div
        className="spotlight-card"
        style={{
          background: 'rgba(255, 255, 255, 0.02)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          padding: '1rem 1.25rem',
          fontSize: '0.85rem',
          color: '#9a9aa0',
          lineHeight: 1.5,
        }}
      >
        <strong style={{ color: '#ffffff' }}>Search Coverage Notice: </strong>
        Meaning search uses a small local embedding model and does not cover all source types. Drug labels
        and guidelines are covered; annotations and research papers are retrieved through keyword and
        recorded relationship paths only.
      </div>
    </section>
  );
};

export default SearchHonestySection;

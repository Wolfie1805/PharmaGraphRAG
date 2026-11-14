import React from 'react';
import { SiteStats } from '../../types';

interface DataSectionProps {
  stats: SiteStats | null;
}

export const DataSection: React.FC<DataSectionProps> = ({ stats }) => {
  if (!stats) {
    return (
      <section id="the-data" className="section-container" aria-labelledby="the-data-heading">
        <span className="section-tag">Authoritative Corpora</span>
        <h2 id="the-data-heading" className="section-heading">
          THE DATA
        </h2>
        <div className="spotlight-card" style={{ textAlign: 'center', padding: '3rem 2rem' }}>
          <p style={{ color: '#9a9aa0', fontSize: '1.1rem', margin: 0 }}>Stats unavailable</p>
        </div>
      </section>
    );
  }

  const pubmedSource = stats.sources?.find((s) => s.pubmed_queries && s.pubmed_queries.length > 0);

  return (
    <section id="the-data" className="section-container" aria-labelledby="the-data-heading">
      <span className="section-tag">Authoritative Corpora</span>
      <h2 id="the-data-heading" className="section-heading">
        THE DATA
      </h2>
      <p className="section-lead">
        Aggregated from published guideline consortia, regulatory drug label annotations, and biomedical literature.
      </p>

      {/* Dynamic Animated Counters */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '1rem',
          marginBottom: '2.5rem',
        }}
      >
        <div className="spotlight-card" style={{ padding: '1.5rem', textAlign: 'center' }}>
          <span style={{ fontSize: '0.8rem', color: '#9a9aa0', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Total Chunks
          </span>
          <div style={{ fontSize: '2rem', fontWeight: 300, color: '#ffffff', fontFamily: 'var(--font-mono)', marginTop: '0.25rem' }}>
            {stats.processed_tables?.chunks != null ? stats.processed_tables.chunks.toLocaleString() : '—'}
          </div>
        </div>

        <div className="spotlight-card" style={{ padding: '1.5rem', textAlign: 'center' }}>
          <span style={{ fontSize: '0.8rem', color: '#9a9aa0', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Scientific Papers
          </span>
          <div style={{ fontSize: '2rem', fontWeight: 300, color: '#ffffff', fontFamily: 'var(--font-mono)', marginTop: '0.25rem' }}>
            {stats.papers?.count != null ? stats.papers.count.toLocaleString() : '—'}
          </div>
        </div>

        <div className="spotlight-card" style={{ padding: '1.5rem', textAlign: 'center' }}>
          <span style={{ fontSize: '0.8rem', color: '#9a9aa0', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Recorded Relationships
          </span>
          <div style={{ fontSize: '2rem', fontWeight: 300, color: '#ffffff', fontFamily: 'var(--font-mono)', marginTop: '0.25rem' }}>
            {stats.relationships?.total != null ? stats.relationships.total.toLocaleString() : '—'}
          </div>
        </div>

        <div className="spotlight-card" style={{ padding: '1.5rem', textAlign: 'center' }}>
          <span style={{ fontSize: '0.8rem', color: '#9a9aa0', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Normalized Entities
          </span>
          <div style={{ fontSize: '2rem', fontWeight: 300, color: '#ffffff', fontFamily: 'var(--font-mono)', marginTop: '0.25rem' }}>
            {stats.processed_tables?.entities != null ? stats.processed_tables.entities.toLocaleString() : '—'}
          </div>
        </div>
      </div>

      {/* Entity Breakdown Sub-bar */}
      {stats.entities_by_type && (
        <div
          className="spotlight-card"
          style={{
            padding: '1.25rem 1.5rem',
            marginBottom: '2.5rem',
            background: 'var(--lp-surface)',
          }}
        >
          <div style={{ fontSize: '0.85rem', color: '#9a9aa0', marginBottom: '0.75rem', fontWeight: 500 }}>
            ENTITIES BY TYPE (STRUCTURED ONTOLOGY)
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1.5rem', fontSize: '0.85rem' }}>
            <div>
              <span style={{ color: '#9a9aa0' }}>Genes: </span>
              <strong style={{ fontFamily: 'var(--font-mono)', color: '#ffffff' }}>
                {stats.entities_by_type.gene != null ? stats.entities_by_type.gene.toLocaleString() : '—'}
              </strong>
            </div>
            <div>
              <span style={{ color: '#9a9aa0' }}>Variants: </span>
              <strong style={{ fontFamily: 'var(--font-mono)', color: '#ffffff' }}>
                {stats.entities_by_type.variant != null ? stats.entities_by_type.variant.toLocaleString() : '—'}
              </strong>
            </div>
            <div>
              <span style={{ color: '#9a9aa0' }}>Haplotypes: </span>
              <strong style={{ fontFamily: 'var(--font-mono)', color: '#ffffff' }}>
                {stats.entities_by_type.haplotype != null ? stats.entities_by_type.haplotype.toLocaleString() : '—'}
              </strong>
            </div>
            <div>
              <span style={{ color: '#9a9aa0' }}>Chemicals: </span>
              <strong style={{ fontFamily: 'var(--font-mono)', color: '#ffffff' }}>
                {stats.entities_by_type.chemical != null ? stats.entities_by_type.chemical.toLocaleString() : '—'}
              </strong>
            </div>
            <div>
              <span style={{ color: '#9a9aa0' }}>Phenotypes: </span>
              <strong style={{ fontFamily: 'var(--font-mono)', color: '#ffffff' }}>
                {stats.entities_by_type.phenotype != null ? stats.entities_by_type.phenotype.toLocaleString() : '—'}
              </strong>
            </div>
          </div>
        </div>
      )}

      {/* Source Cards from site_stats.json */}
      <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '1.3rem', color: '#ffffff', marginBottom: '1.25rem' }}>
        INGESTED SOURCE REPOSITORIES
      </h3>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem', marginBottom: '2.5rem' }}>
        {stats.sources?.map((source) => (
          <div key={source.name} className="spotlight-card" style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <h4 style={{ margin: 0, fontSize: '1.1rem', color: '#ffffff', fontFamily: 'var(--font-heading)' }}>
                {source.name}
              </h4>
              {source.date_checked && (
                <span style={{ fontSize: '0.75rem', color: '#9a9aa0', fontFamily: 'var(--font-mono)' }}>
                  Checked: {source.date_checked}
                </span>
              )}
            </div>

            <p style={{ margin: 0, fontSize: '0.88rem', color: '#9a9aa0', lineHeight: 1.5 }}>
              {source.description}
            </p>

            {/* Inconsistent license key handling & dual license display */}
            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.75rem', borderRadius: '6px', fontSize: '0.8rem', border: '1px solid rgba(255,255,255,0.06)' }}>
              {source.site_footer_license && (
                <div style={{ marginBottom: '0.35rem' }}>
                  <span style={{ color: '#9a9aa0' }}>Site Footer License: </span>
                  <span style={{ color: '#ffffff', fontFamily: 'var(--font-mono)' }}>{source.site_footer_license}</span>
                </div>
              )}

              {source.archive_bundled_license && (
                <div style={{ marginBottom: '0.35rem' }}>
                  <span style={{ color: '#9a9aa0' }}>Archive Bundled License: </span>
                  <span style={{ color: '#ffffff', fontFamily: 'var(--font-mono)' }}>{source.archive_bundled_license}</span>
                </div>
              )}

              {source.license && !source.site_footer_license && (
                <div style={{ marginBottom: '0.35rem' }}>
                  <span style={{ color: '#9a9aa0' }}>License: </span>
                  <span style={{ color: '#ffffff', fontFamily: 'var(--font-mono)' }}>{source.license}</span>
                </div>
              )}

              {source.discrepancy_unresolved && (
                <div style={{ color: '#f59e0b', marginBottom: '0.35rem', fontWeight: 500 }}>
                  Discrepancy unresolved between site footer and bundled license.
                </div>
              )}

              {source.working_assumption && (
                <div style={{ color: '#9a9aa0', fontStyle: 'italic', marginBottom: '0.35rem' }}>
                  Working assumption: {source.working_assumption}
                </div>
              )}
            </div>

            {/* Verbatim License Notes */}
            {source.license_notes && source.license_notes.length > 0 && (
              <div style={{ fontSize: '0.78rem', color: '#9a9aa0', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '0.5rem' }}>
                <span style={{ fontWeight: 600, color: 'rgba(255,255,255,0.7)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Verbatim License Notes:
                </span>
                <ul style={{ margin: '0.35rem 0 0 0', paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  {source.license_notes.map((note, idx) => (
                    <li key={idx}>
                      <span style={{ fontFamily: 'var(--font-mono)', color: 'rgba(255,255,255,0.5)' }}>[{note.location}] </span>
                      <span style={{ color: '#e5e5e8' }}>"{note.quote}"</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* PubMed Queries Table */}
      {pubmedSource?.pubmed_queries && pubmedSource.pubmed_queries.length > 0 && (
        <div className="spotlight-card" style={{ marginBottom: '2.5rem', overflowX: 'auto' }}>
          <h4 style={{ margin: '0 0 1rem 0', fontSize: '1.05rem', color: '#ffffff', fontFamily: 'var(--font-heading)' }}>
            PUBMED SEARCH QUERIES AND RETRIEVAL COUNTS
          </h4>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#9a9aa0' }}>
                <th style={{ padding: '0.5rem 0.75rem', fontWeight: 500 }}>Pair ID</th>
                <th style={{ padding: '0.5rem 0.75rem', fontWeight: 500 }}>Exact Query</th>
                <th style={{ padding: '0.5rem 0.75rem', fontWeight: 500 }}>ESearch Count</th>
                <th style={{ padding: '0.5rem 0.75rem', fontWeight: 500 }}>Retrieval Date</th>
              </tr>
            </thead>
            <tbody>
              {pubmedSource.pubmed_queries.map((q) => (
                <tr key={q.pair_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <td style={{ padding: '0.6rem 0.75rem', fontFamily: 'var(--font-mono)', color: '#ffffff' }}>
                    {q.pair_id}
                  </td>
                  <td style={{ padding: '0.6rem 0.75rem', fontFamily: 'var(--font-mono)', color: '#9a9aa0', fontSize: '0.78rem' }}>
                    {q.query}
                  </td>
                  <td style={{ padding: '0.6rem 0.75rem', fontFamily: 'var(--font-mono)', color: '#ffffff' }}>
                    {q.esearch_count.toLocaleString()}
                  </td>
                  <td style={{ padding: '0.6rem 0.75rem', fontFamily: 'var(--font-mono)', color: '#9a9aa0' }}>
                    {q.retrieval_date}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* What Is NOT Included List */}
      <div
        className="spotlight-card"
        style={{
          background: '#151314',
          borderLeft: '3px solid rgba(255,255,255,0.2)',
          padding: '1.5rem',
        }}
      >
        <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '1rem', color: '#ffffff', fontFamily: 'var(--font-heading)' }}>
          WHAT IS NOT INCLUDED
        </h4>
        <ul style={{ margin: 0, paddingLeft: '1.25rem', color: '#9a9aa0', fontSize: '0.88rem', lineHeight: 1.6 }}>
          <li>Full-text closed-access journal articles (abstracts and excerpts only).</li>
          <li>Commercial proprietary genomics databases or paywalled clinical decision suites.</li>
          <li>Electronic medical health records or patient-identifiable healthcare data.</li>
          <li>Direct-to-consumer genetic raw sequencing data.</li>
        </ul>
      </div>
    </section>
  );
};

export default DataSection;

import React from 'react';

export const LimitsRoadmapSection: React.FC = () => {
  return (
    <section id="limits-roadmap" className="section-container" aria-labelledby="limits-heading">
      <span className="section-tag">Engineering Transparency</span>
      <h2 id="limits-heading" className="section-heading">
        KNOWN LIMITS & ROADMAP
      </h2>
      <p className="section-lead">
        Documenting known current boundaries and planned enhancements for future releases.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '2rem' }}>
        {/* Known Limits Card */}
        <div className="spotlight-card" style={{ borderTop: '3px solid rgba(255, 255, 255, 0.2)' }}>
          <h3 style={{ fontFamily: 'var(--font-heading)', color: '#ffffff', fontSize: '1.2rem', marginBottom: '1rem' }}>
            KNOWN LIMITS
          </h3>
          <ul style={{ margin: 0, paddingLeft: '1.25rem', color: '#9a9aa0', fontSize: '0.88rem', lineHeight: 1.6, display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <li>
              <strong style={{ color: '#ffffff' }}>Brand names not recognized outside NRCeS: </strong>
              Indian brand names are recognized only where they appear in the NRCeS release, and only to list ingredients.
            </li>
            <li>
              <strong style={{ color: '#ffffff' }}>Annotation records lack curation dates: </strong>
              Curated repository entries frequently omit the date when the annotation was logged.
            </li>
            <li>
              <strong style={{ color: '#ffffff' }}>No full paper text: </strong>
              Literature retrieval is restricted to titles, abstracts, and open excerpts; paywalled articles are not mirrored.
            </li>
            <li>
              <strong style={{ color: '#ffffff' }}>Extractive summaries only: </strong>
              Answers are verbatim passages from sources; no text-writing model generates prose by default.
            </li>
            <li>
              <strong style={{ color: '#ffffff' }}>Partial meaning search coverage: </strong>
              Vector similarity embeddings currently cover drug labels and guidelines only, omitting annotations and papers.
            </li>
          </ul>
        </div>

        {/* Future Roadmap Card */}
        <div className="spotlight-card" style={{ borderTop: '3px solid rgba(255, 255, 255, 0.4)' }}>
          <h3 style={{ fontFamily: 'var(--font-heading)', color: '#ffffff', fontSize: '1.2rem', marginBottom: '1rem' }}>
            DEVELOPMENT ROADMAP
          </h3>
          <ul style={{ margin: 0, paddingLeft: '1.25rem', color: '#9a9aa0', fontSize: '0.88rem', lineHeight: 1.6, display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <li>
              <strong style={{ color: '#ffffff' }}>Expanded Meaning Search: </strong>
              Full vector indexing across literature abstracts and curated annotation notes.
            </li>
            <li>
              <strong style={{ color: '#ffffff' }}>Additional Evidence Sources: </strong>
              Ingestion of international consortia data such as DPWG (Dutch Pharmacogenetics Working Group).
            </li>
            <li>
              <strong style={{ color: '#ffffff' }}>Continuous Label Updates: </strong>
              Automated pipelines for ingesting updated drug label tables.
            </li>
            <li>
              <strong style={{ color: '#ffffff' }}>Advanced Relation Extraction: </strong>
              Automated identification of multi-variant interaction effects.
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
};

export default LimitsRoadmapSection;

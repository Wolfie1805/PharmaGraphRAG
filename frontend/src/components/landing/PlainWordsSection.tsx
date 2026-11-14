import React, { useState } from 'react';

interface GlossaryEntry {
  term: string;
  badge: string;
  definition: string;
}

const GLOSSARY_DATA: GlossaryEntry[] = [
  {
    term: 'Gene',
    badge: 'Biological Code',
    definition:
      'A specific segment of DNA that provides cellular instructions for building proteins, drug-metabolizing enzymes, or transporters.',
  },
  {
    term: 'Variant',
    badge: 'Sequence Variation',
    definition:
      'A specific difference or alternate spelling in a DNA sequence among individuals, such as single nucleotide changes.',
  },
  {
    term: 'Star Allele',
    badge: 'Nomenclature',
    definition:
      'A standardized pharmacogenomic shorthand symbol (such as *2, *3, or *17) representing a recognized functional gene haplotype.',
  },
  {
    term: 'Annotation',
    badge: 'Curated Evidence',
    definition:
      'A structured summary of published scientific literature documenting an observed relationship between a variant and drug response.',
  },
];

export const PlainWordsSection: React.FC = () => {
  const [hoveredTerm, setHoveredTerm] = useState<string | null>(null);

  return (
    <section id="what-it-is" className="section-container" aria-labelledby="plain-words-heading">
      <span className="section-tag">Concepts Explained</span>
      <h2 id="plain-words-heading" className="section-heading">
        WHAT IT IS, IN PLAIN WORDS
      </h2>
      <p className="section-lead">
        Pharmacogenomics investigates how individual genetic differences influence the way
        human bodies respond to medications.
      </p>

      <div className="plain-words-grid">
        <div className="analogy-card">
          <div className="analogy-item">
            <h3 className="analogy-title">A medicine is the key</h3>
            <p className="analogy-desc">
              Every therapeutic molecule is designed to interact with specific cellular
              targets, receptors, or metabolic pathways.
            </p>
          </div>

          <div className="analogy-item">
            <h3 className="analogy-title">A gene is the instruction</h3>
            <p className="analogy-desc">
              Your cellular DNA contains the precise molecular recipes to manufacture the
              enzymes and proteins that process that key.
            </p>
          </div>

          <div className="analogy-item">
            <h3 className="analogy-title">People carry different spellings</h3>
            <p className="analogy-desc">
              Natural variations alter how quickly or effectively those enzymes operate,
              changing how a medicine is cleared or activated.
            </p>
          </div>

          <div className="analogy-item">
            <h3 className="analogy-title">This field is pharmacogenomics</h3>
            <p className="analogy-desc">
              By mapping the scientific evidence between genetic variants and drug responses,
              researchers can understand variations in efficacy and adverse reactions.
            </p>
          </div>
        </div>

        <div className="glossary-card-list" role="region" aria-label="Pharmacogenomics Glossary">
          {GLOSSARY_DATA.map((item) => {
            const isActive = hoveredTerm === item.term;
            return (
              <div
                key={item.term}
                className={`glossary-item ${isActive ? 'active' : ''}`}
                onMouseEnter={() => setHoveredTerm(item.term)}
                onMouseLeave={() => setHoveredTerm(null)}
                onFocus={() => setHoveredTerm(item.term)}
                onBlur={() => setHoveredTerm(null)}
                tabIndex={0}
                role="article"
                aria-label={`${item.term} definition`}
              >
                <div className="glossary-header">
                  <span className="glossary-term">{item.term}</span>
                  <span className="glossary-badge">{item.badge}</span>
                </div>
                <p className="glossary-definition" style={{ margin: 0, fontSize: '0.9rem', color: '#9a9aa0' }}>
                  {item.definition}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};

export default PlainWordsSection;

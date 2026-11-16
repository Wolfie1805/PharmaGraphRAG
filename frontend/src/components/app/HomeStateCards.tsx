import React from 'react';

interface HomeStateCardsProps {
  onSelectExample: (query: string, hints?: string[]) => void;
  disabled?: boolean;
}

interface ShapeCardConfig {
  id: string;
  title: string;
  template: string;
  description: string;
  bullets: string[];
  exampleText: string;
  exampleQuery: string;
}

const SUPPORTED_SHAPES: ShapeCardConfig[] = [
  {
    id: 'medicine-overview',
    title: 'A medicine',
    template: '[Medicine name]',
    description: 'Overview of all gene interactions and curated evidence for a medicine.',
    bullets: [
      'Interacting genes with curated association levels',
      'Chunk counts across guidelines, labels, and annotations',
      'One-click access to open any specific gene-drug pair',
    ],
    exampleText: 'Try clopidogrel',
    exampleQuery: 'clopidogrel',
  },
  {
    id: 'gene-overview',
    title: 'A gene',
    template: '[Gene symbol]',
    description: 'Overview of all medicine interactions and evidence for a gene.',
    bullets: [
      'Interacting medicines with curated association levels',
      'Counts for clinical guidelines, drug labels, and papers',
      'One-click navigation into any specific pair detail',
    ],
    exampleText: 'Try CYP2C19',
    exampleQuery: 'CYP2C19',
  },
  {
    id: 'pair-detail',
    title: 'A gene and a medicine',
    template: '[Gene] [Medicine]',
    description: 'Detailed clinical guidelines, regulatory labels, and variant findings.',
    bullets: [
      'CPIC and DPWG clinical recommendations and testing levels',
      'FDA and EMA drug label annotations and biomarker status',
      'Grounded clinical citations with exact source sentences',
    ],
    exampleText: 'Try CYP2C19 clopidogrel',
    exampleQuery: 'CYP2C19 clopidogrel',
  },
  {
    id: 'variant-detail',
    title: 'A variant and a medicine',
    template: '[Variant/rsID] [Medicine]',
    description: 'Findings for a specific variant or star allele with a medicine.',
    bullets: [
      'Clinical significance and direction of effect',
      'Phenotype category and study population types',
      'Direct link to PubMed citations and relationship records',
    ],
    exampleText: 'Try rs4244285 clopidogrel',
    exampleQuery: 'rs4244285 clopidogrel',
  },
];

export const HomeStateCards: React.FC<HomeStateCardsProps> = ({
  onSelectExample,
  disabled = false,
}) => {
  return (
    <section className="home-state-container" aria-label="Supported Query Formats">
      <div className="home-state-header">
        <h2 className="home-state-title">What can I ask?</h2>
        <p className="home-state-subtitle">
          Explore pharmacogenomic interactions using exact biomedical entities. Select an example below or enter your own search.
        </p>
      </div>

      <div className="home-cards-grid" role="list">
        {SUPPORTED_SHAPES.map((shape) => (
          <article key={shape.id} className="home-shape-card" role="listitem">
            <div className="shape-card-top">
              <span className="shape-card-title">{shape.title}</span>
              <code className="shape-card-template">{shape.template}</code>
            </div>
            <p className="shape-card-desc">{shape.description}</p>
            <div className="shape-card-bullets">
              <span className="shape-bullets-header">What you will get:</span>
              <ul className="shape-bullets-list">
                {shape.bullets.map((bullet, idx) => (
                  <li key={idx} className="shape-bullet-item">{bullet}</li>
                ))}
              </ul>
            </div>
            <button
              type="button"
              className="btn-shape-example"
              disabled={disabled}
              onClick={() => onSelectExample(shape.exampleQuery)}
            >
              <span>{shape.exampleText}</span>
              <span className="btn-arrow" aria-hidden="true">&rarr;</span>
            </button>
          </article>
        ))}

        {/* Fifth Card: Quieter "Not supported yet" */}
        <article className="home-shape-card card-unsupported" role="listitem">
          <div className="shape-card-top">
            <span className="shape-card-title">Not supported yet</span>
            <span className="shape-unsupported-tag">Out of scope</span>
          </div>
          <p className="shape-card-desc">
            To prevent unsafe speculation or ungrounded extrapolation, this system does not support:
          </p>
          <div className="shape-card-bullets">
            <ul className="shape-bullets-list">
              <li className="shape-bullet-item">Personal medical advice, clinical decisions, or dosing instructions</li>
              <li className="shape-bullet-item">Multi-gene polygenic risk calculations or whole exome panels</li>
              <li className="shape-bullet-item">Queries that do not contain a recognized gene, chemical, or variant</li>
            </ul>
          </div>
          <div className="unsupported-footer-note">
            Always consult a qualified healthcare professional before making medication decisions.
          </div>
        </article>
      </div>
    </section>
  );
};

import React, { useState } from 'react';
import { EntityCandidate, PromptTemplateItem, ResolvedEntity } from '../../types';

// ============================================================================
// 1. Ambiguity Picker Card (with Glow Button Style)
// ============================================================================

interface AmbiguityPickerProps {
  ambiguousEntity: ResolvedEntity;
  onSelectCandidate: (candidateId: string, candidateName: string, originalTerm?: string) => void;
}

export const AmbiguityPickerCard: React.FC<AmbiguityPickerProps> = ({
  ambiguousEntity,
  onSelectCandidate,
}) => {
  const candidates: EntityCandidate[] = ambiguousEntity.candidates || [];
  const termName = ambiguousEntity.name || ambiguousEntity.query;

  return (
    <div className="edge-card card-ambiguity" role="region" aria-label="Ambiguity Resolution">
      <div className="edge-card-header">
        <span className="edge-icon" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </span>
        <div>
          <h4 className="edge-card-title">Ambiguity Detected: &ldquo;{termName}&rdquo;</h4>
          <p className="edge-card-lead">
            This name maps to multiple distinct clinical entities in the database. Choose the candidate you meant:
          </p>
        </div>
      </div>

      <div className="ambiguity-candidate-list" role="list">
        {candidates.map((cand) => {
          const isAllele = cand.entity_type.toLowerCase() === 'haplotype' || cand.display_name.includes('*');
          return (
            <div key={cand.canonical_id} className="candidate-item" role="listitem">
              <div className="candidate-info">
                <div className="candidate-name-row">
                  <span className={`candidate-display-name ${isAllele ? 'font-mono' : ''}`}>
                    {cand.display_name}
                  </span>
                  <span className="candidate-type-badge">{cand.entity_type}</span>
                </div>
                <div className="candidate-meta-row">
                  <span className="candidate-cid font-mono">{cand.canonical_id}</span>
                  {cand.defined_by && (
                    <span className="candidate-source">Defined by: {cand.defined_by}</span>
                  )}
                </div>
              </div>
              <button
                type="button"
                className="btn-select-candidate btn-glow"
                onClick={() => onSelectCandidate(cand.canonical_id, cand.display_name, termName)}
              >
                <span>Select</span>
                <span className="btn-arrow" aria-hidden="true">&rarr;</span>
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ============================================================================
// 2. Refusal Card (Calm Amber Panel with Supported Templates)
// ============================================================================

interface RefusalCardProps {
  answer: string;
  flags?: string[];
  templates?: PromptTemplateItem[];
  onSelectTemplate?: (query: string) => void;
}

const DEFAULT_TEMPLATES: PromptTemplateItem[] = [
  {
    name: 'A medicine',
    shape: '[Medicine]',
    template: '[Medicine name]',
    example: 'clopidogrel',
    description: 'Overview of all gene interactions for a medicine.',
  },
  {
    name: 'A gene',
    shape: '[Gene]',
    template: '[Gene symbol]',
    example: 'CYP2C19',
    description: 'Overview of all medicine interactions for a gene.',
  },
  {
    name: 'A gene and a medicine',
    shape: '[Gene] [Medicine]',
    template: '[Gene] [Medicine]',
    example: 'CYP2C19 clopidogrel',
    description: 'Detailed clinical guidelines and variant findings.',
  },
  {
    name: 'A variant and a medicine',
    shape: '[Variant] [Medicine]',
    template: '[Variant/rsID] [Medicine]',
    example: 'rs4244285 clopidogrel',
    description: 'Detailed evidence for a specific variant-drug pair.',
  },
];

export const RefusalCard: React.FC<RefusalCardProps> = ({
  answer,
  flags = [],
  templates = DEFAULT_TEMPLATES,
  onSelectTemplate,
}) => {
  return (
    <div className="edge-card card-refusal" role="alert" aria-label="Clinical Refusal Notice">
      <div className="edge-card-header">
        <span className="edge-icon icon-shield" aria-hidden="true">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        </span>
        <div>
          <h4 className="edge-card-title refusal-title">Research Prototype Safety Boundary</h4>
          <p className="refusal-badge">Evidence Explorer &bull; Not a prescribing tool</p>
        </div>
      </div>

      <div className="refusal-content">
        <p className="refusal-body-text">{answer}</p>
      </div>

      <div className="refusal-explanation">
        <strong>Safety Policy:</strong> This system is a pharmacogenomics evidence explorer, not a prescribing tool. It does not provide direct clinical management advice or personal dosing instructions.
      </div>

      {templates.length > 0 && (
        <div className="refusal-templates-block">
          <span className="refusal-templates-title">Supported query formats you can explore:</span>
          <div className="templates-mini-grid">
            {templates.map((tmpl) => (
              <div key={tmpl.name} className="template-mini-card">
                <span className="tmpl-name">{tmpl.name}</span>
                <code className="tmpl-shape font-mono">{tmpl.template}</code>
                <p className="tmpl-desc">{tmpl.description}</p>
                {onSelectTemplate && (
                  <button
                    type="button"
                    className="btn-tmpl-example"
                    onClick={() => onSelectTemplate(tmpl.example)}
                  >
                    <span>Try "{tmpl.example}"</span>
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {flags.length > 0 && (
        <div className="refusal-flags-row">
          <span className="flags-label">Safety Flags:</span>
          {flags.map((flag) => (
            <span key={flag} className="refusal-flag-pill">
              {flag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

// ============================================================================
// 3. Unrecognized Entity Card (Calm Blue Panel with Supported Templates)
// ============================================================================

interface UnrecognizedEntityProps {
  term?: string;
  templates?: PromptTemplateItem[];
  onSelectTemplate?: (query: string) => void;
}

export const UnrecognizedEntityCard: React.FC<UnrecognizedEntityProps> = ({
  term,
  templates = DEFAULT_TEMPLATES,
  onSelectTemplate,
}) => {
  return (
    <div className="edge-card card-unrecognized" role="region" aria-label="Unrecognized Entity Notice">
      <div className="edge-card-header">
        <span className="edge-icon icon-info" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
            <line x1="8" y1="11" x2="14" y2="11" />
          </svg>
        </span>
        <div>
          <h4 className="edge-card-title">Entity Not Found in Pharmacogenomics Data</h4>
          <p className="edge-card-lead">
            {term
              ? `We could not match "${term}" to a recognized gene, chemical, or variant.`
              : 'No recognized gene, chemical, or variant was found in your query.'}
          </p>
        </div>
      </div>

      <div className="edge-body-text">
        ClinPGx and PharmGKB index standard gene symbols (e.g. CYP2C19), variant rsIDs (e.g. rs4244285), star alleles (e.g. *2), and active drug ingredients (e.g. clopidogrel). Check the spelling or try one of the supported query formats below.
      </div>

      {templates.length > 0 && (
        <div className="unrecognized-templates-block">
          <span className="templates-grid-header">Supported Query Shapes:</span>
          <div className="templates-mini-grid">
            {templates.map((tmpl) => (
              <div key={tmpl.name} className="template-mini-card">
                <span className="tmpl-name">{tmpl.name}</span>
                <code className="tmpl-shape font-mono">{tmpl.template}</code>
                <p className="tmpl-desc">{tmpl.description}</p>
                {onSelectTemplate && (
                  <button
                    type="button"
                    className="btn-tmpl-example"
                    onClick={() => onSelectTemplate(tmpl.example)}
                  >
                    <span>Try "{tmpl.example}"</span>
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// 4. Insufficient Evidence Card (Calm Grey Panel)
// ============================================================================

interface InsufficientEvidenceProps {
  totalItems?: number;
  minRequired?: number;
}

export const InsufficientEvidenceCard: React.FC<InsufficientEvidenceProps> = ({
  totalItems = 0,
  minRequired = 3,
}) => {
  return (
    <div className="edge-card card-insufficient" role="region" aria-label="Insufficient Evidence Notice">
      <div className="edge-card-header">
        <span className="edge-icon" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#9a9aa0" strokeWidth="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        </span>
        <div>
          <h4 className="edge-card-title">Insufficient Curated Evidence</h4>
          <p className="edge-card-lead">
            Retrieved {totalItems} grounded items (minimum required: {minRequired}) for this query.
          </p>
        </div>
      </div>

      <div className="edge-body-text">
        Under PharmaGraph&rsquo;s strict grounding policy, no synthetic conclusions are generated when evidence falls short of the threshold. Try searching for a canonical gene symbol or active drug ingredient.
      </div>
    </div>
  );
};

// ============================================================================
// 5. Backend Offline Card (Banner with Health Check Retry)
// ============================================================================

interface BackendOfflineProps {
  url?: string;
  onRetry: () => void;
  retrying?: boolean;
}

export const BackendOfflineCard: React.FC<BackendOfflineProps> = ({
  url = 'localhost:8000',
  onRetry,
  retrying = false,
}) => {
  return (
    <div className="edge-card card-offline" role="alert" aria-label="Backend Service Unreachable">
      <div className="edge-card-header">
        <span className="edge-icon" aria-hidden="true">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2">
            <line x1="1" y1="1" x2="23" y2="23" />
            <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
            <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
            <path d="M10.71 5.05A16 16 0 0 1 22.58 9" />
            <path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" />
            <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
            <line x1="12" y1="20" x2="12.01" y2="20" />
          </svg>
        </span>
        <div>
          <h4 className="edge-card-title offline-title">Backend Service Offline</h4>
          <p className="edge-card-lead">
            Unable to connect to the API at {url}. The backend daemon may be initializing or stopped.
          </p>
        </div>
      </div>

      <div className="offline-action-row">
        <button
          type="button"
          className="btn-retry"
          disabled={retrying}
          onClick={onRetry}
        >
          {retrying ? 'Checking connection...' : 'Retry Connection'}
        </button>
      </div>
    </div>
  );
};

// ============================================================================
// 6. Persistent "How to read this" Drawer / Card
// ============================================================================

export const HowToReadThisCard: React.FC = () => {
  const [isOpen, setIsOpen] = useState<boolean>(false);

  return (
    <aside className="how-to-read-card" aria-label="How to read pharmacogenomics data">
      <button
        type="button"
        className="how-to-read-toggle-btn"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
      >
        <span className="toggle-btn-icon" aria-hidden="true">ℹ</span>
        <span className="toggle-btn-text">How to read this</span>
        <span className="toggle-btn-chevron" aria-hidden="true">{isOpen ? '▲' : '▼'}</span>
      </button>

      {isOpen && (
        <div className="how-to-read-content">
          <div className="read-section">
            <h5 className="read-section-title">Overview vs. Detail View</h5>
            <p className="read-section-desc">
              <strong>Overview:</strong> When querying a single medicine or gene, a table shows all recorded interacting partners with counts of clinical guidelines, labels, and variant annotations. Click &ldquo;Open&rdquo; on any row to see full details.
            </p>
            <p className="read-section-desc">
              <strong>Detail:</strong> When querying a gene-medicine pair or variant, the view breaks down exact guidelines (CPIC/DPWG), regulatory drug labels (FDA/EMA), variant findings, and cited literature.
            </p>
          </div>

          <div className="read-section">
            <h5 className="read-section-title">What is a Star Allele (*)?</h5>
            <p className="read-section-desc">
              Star alleles (e.g. <code className="font-mono">CYP2C19*2</code>) denote specific genetic variants or haplotypes in pharmacogenes that alter enzyme function, leading to poor, intermediate, normal, or rapid metabolizer phenotypes.
            </p>
          </div>

          <div className="read-section">
            <h5 className="read-section-title">Citation Verification</h5>
            <p className="read-section-desc">
              Every assertion in extractive summaries is verified against retrieved chunks. Unverified claims are automatically excluded.
            </p>
          </div>
        </div>
      )}
    </aside>
  );
};

// ============================================================================
// 7. Skeleton Loading State
// ============================================================================

interface SkeletonLoadingProps {
  reducedEffects?: boolean;
}

export const SkeletonLoading: React.FC<SkeletonLoadingProps> = ({ reducedEffects }) => {
  const shimmerClass = reducedEffects ? 'skeleton-static' : 'skeleton-shimmer';

  return (
    <div className="skeleton-loading-container" aria-label="Loading search results" role="status">
      <div className={`skeleton-card skeleton-glance ${shimmerClass}`}>
        <div className="skeleton-line line-title" />
        <div className="skeleton-pills-row">
          <div className="skeleton-pill" />
          <div className="skeleton-pill" />
          <div className="skeleton-pill" />
        </div>
      </div>

      <div className={`skeleton-card skeleton-summary ${shimmerClass}`}>
        <div className="skeleton-line line-header" />
        <div className="skeleton-line line-body" />
        <div className="skeleton-line line-body short" />
        <div className="skeleton-line line-body medium" />
      </div>

      <div className={`skeleton-card skeleton-chart ${shimmerClass}`}>
        <div className="skeleton-line line-header" />
        <div className="skeleton-bar-row" />
        <div className="skeleton-bar-row" />
        <div className="skeleton-bar-row" />
      </div>
    </div>
  );
};

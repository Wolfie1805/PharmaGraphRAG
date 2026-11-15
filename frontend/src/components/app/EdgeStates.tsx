import React from 'react';
import { EntityCandidate, ResolvedEntity } from '../../types';

// ============================================================================
// 1. Ambiguity Picker Card
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
            This surface form maps to multiple distinct clinical entities in the knowledge base.
            Choose which one you meant:
          </p>
          <button
            type="button"
            className="btn-resolve-ambiguity"
            aria-label={`Resolve ambiguous entity ${termName}`}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--dim-warning-text)',
              fontSize: '0.8rem',
              cursor: 'pointer',
              padding: '0.2rem 0',
            }}
          >
            Resolve ambiguous entity {termName}
          </button>
        </div>
      </div>

      <div className="ambiguity-candidate-list" role="list">
        {candidates.map((cand) => (
          <div key={cand.canonical_id} className="candidate-item" role="listitem">
            <div className="candidate-info">
              <div className="candidate-name-row">
                <span className="candidate-type-badge">{cand.entity_type}</span>
              </div>
              <div className="candidate-meta-row">
                <span className="candidate-cid">ID: {cand.canonical_id}</span>
                {cand.defined_by && (
                  <span className="candidate-source">Defined by: {cand.defined_by}</span>
                )}
              </div>
            </div>
            <button
              type="button"
              className="btn-select-candidate"
              onClick={() => onSelectCandidate(cand.canonical_id, cand.display_name, termName)}
            >
              {cand.display_name}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// 2. Refusal Card (Clinical Safety Boundary)
// ============================================================================

interface RefusalCardProps {
  answer: string;
  flags?: string[];
}

export const RefusalCard: React.FC<RefusalCardProps> = ({ answer, flags = [] }) => {
  return (
    <div className="edge-card card-refusal" role="alert" aria-label="Clinical Refusal Notice">
      <div className="edge-card-header">
        <span className="edge-icon icon-shield" aria-hidden="true">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        </span>
        <div>
          <h4 className="edge-card-title refusal-title">Clinical Advice Safety Boundary</h4>
          <p className="refusal-badge">Request Intercepted &bull; Refusal Policy</p>
        </div>
      </div>

      <div className="refusal-content">
        <p className="refusal-body-text">{answer}</p>
      </div>

      <div className="refusal-explanation">
        <strong>Safety Guardrail Explanation:</strong> PharmaGraph is an evidence-grounded research tool.
        It cannot and does not offer direct treatment recommendations, emergency advice, or personal dosing calculations.
        If you are experiencing a medical condition, please contact a licensed clinician or emergency services immediately.
      </div>

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
// 3. Unrecognized Entity Card
// ============================================================================

interface UnrecognizedEntityProps {
  term: string;
  suggestedSpelling?: string;
  onSelectSuggestion?: (term: string) => void;
}

export const UnrecognizedEntityCard: React.FC<UnrecognizedEntityProps> = ({
  term,
  suggestedSpelling,
  onSelectSuggestion,
}) => {
  return (
    <div className="edge-card card-unrecognized" role="region" aria-label="Unrecognized Entity Notice">
      <div className="edge-card-header">
        <span className="edge-icon" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#9a9aa0" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
            <line x1="8" y1="11" x2="14" y2="11" />
          </svg>
        </span>
        <div>
          <h4 className="edge-card-title">Entity Not Found in Pharmacogenomics Database</h4>
          <p className="edge-card-lead">
            We could not find &ldquo;{term}&rdquo; in the curated PGx database.
          </p>
        </div>
      </div>

      <div className="edge-body-text">
        The database indexes genes, alleles, star variants, rsIDs, and chemical substances from CPIC, PharmGKB, and ClinPGx.
        Make sure the term is spelled according to standard HGNC or pharmacogenomic nomenclature.
      </div>

      {suggestedSpelling && onSelectSuggestion && (
        <div className="suggested-correction-box">
          <span>Did you mean:</span>
          <button
            type="button"
            className="btn-correction"
            onClick={() => onSelectSuggestion(suggestedSpelling)}
          >
            {suggestedSpelling}
          </button>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// 4. Insufficient Evidence Card
// ============================================================================

export const InsufficientEvidenceCard: React.FC = () => {
  return (
    <div className="edge-card card-insufficient" role="region" aria-label="Insufficient Evidence Notice">
      <div className="edge-card-header">
        <span className="edge-icon" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        </span>
        <div>
          <h4 className="edge-card-title">Insufficient Curated Evidence</h4>
          <p className="edge-card-lead">
            No curated clinical guidelines or approved drug labels were found for this specific gene-drug pair.
          </p>
        </div>
      </div>

      <div className="edge-body-text">
        Under PharmaGraph&rsquo;s strict grounding policy, the system does not extrapolate or generate unverified clinical conclusions.
        Try refining your query to a canonical gene symbol or active drug ingredient.
      </div>
    </div>
  );
};

// ============================================================================
// 5. Backend Offline Card
// ============================================================================

interface BackendOfflineProps {
  url?: string;
  onRetry: () => void;
}

export const BackendOfflineCard: React.FC<BackendOfflineProps> = ({
  url = 'http://localhost:8000/api',
  onRetry,
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
          <h4 className="edge-card-title offline-title">Backend Service Unreachable</h4>
          <p className="edge-card-lead">
            Unable to communicate with the retrieval API at {url}. Check if the API service is running.
          </p>
        </div>
      </div>

      <div className="offline-action-row">
        <button type="button" className="btn-retry" onClick={onRetry}>
          Retry Connection
        </button>
      </div>
    </div>
  );
};

// ============================================================================
// 6. Skeleton Loading State
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

// ============================================================================
// 7. Empty State Welcome Card
// ============================================================================

interface EmptyWelcomeProps {
  onSelectStarter: (question: string) => void;
}

export const EmptyWelcomeCard: React.FC<EmptyWelcomeProps> = ({ onSelectStarter }) => {
  const starterQuestions = [
    'What is the relationship between CYP2C19 and clopidogrel?',
    'warfarin VKORC1',
    'Is HLA-B*57:01 associated with abacavir hypersensitivity?',
  ];

  return (
    <div className="empty-welcome-card" aria-label="Welcome and System Overview">
      <div className="welcome-hero-header">
        <h2 className="welcome-title">Evidence-Grounded Pharmacogenomics</h2>
        <p className="welcome-lead">
          Direct multi-path retrieval across CPIC clinical guidelines, PharmGKB variant annotations,
          ClinPGx drug labels, and PubMed literature without generative model hallucination.
        </p>
      </div>

      <div className="welcome-starters-section">
        <h3 className="starters-section-heading">Suggested Inquiries to Explore:</h3>
        <div className="welcome-starters-grid">
          {starterQuestions.map((q) => (
            <button
              key={q}
              type="button"
              className="welcome-starter-card"
              onClick={() => onSelectStarter(q)}
            >
              <span className="starter-query-text">{q}</span>
              <span className="starter-action-arrow">Run search &rarr;</span>
            </button>
          ))}
        </div>
      </div>

      <div className="welcome-architecture-summary">
        <div className="arch-feature">
          <strong className="arch-feature-title">Pure Extractive Synthesis</strong>
          <span className="arch-feature-desc">All answer text is strictly assembled from source quotes.</span>
        </div>
        <div className="arch-feature">
          <strong className="arch-feature-title">Multi-Path RRF Fusion</strong>
          <span className="arch-feature-desc">Combines semantic vector search, BM25 keyword matching, and relationship graph traversals.</span>
        </div>
        <div className="arch-feature">
          <strong className="arch-feature-title">Auditable Provenance</strong>
          <span className="arch-feature-desc">Every claim links to exact canonical identifiers and primary source IDs.</span>
        </div>
      </div>
    </div>
  );
};

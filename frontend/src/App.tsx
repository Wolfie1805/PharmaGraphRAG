import React, { useState } from 'react';
import { askQuestion } from './api';
import { AskResponse } from './types';
import { EntityChips } from './components/EntityChips';
import { AnswerPanel } from './components/AnswerPanel';
import { EvidencePanel } from './components/EvidencePanel';
import { RefusalPanel } from './components/RefusalPanel';

function replaceAmbiguousTerm(question: string, originalTerm: string | undefined, replacement: string): string {
  const trimmed = question.trim();
  if (originalTerm && trimmed) {
    const escaped = originalTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`\\b${escaped}\\b`, 'i');
    if (regex.test(trimmed)) {
      return trimmed.replace(regex, replacement);
    }
  }
  return trimmed ? `${trimmed} ${replacement}` : replacement;
}

export const App: React.FC = () => {
  const [question, setQuestion] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [highlightedSourceId, setHighlightedSourceId] = useState<string | null>(null);

  const handleSubmit = async (qToAsk?: string) => {
    const q = (qToAsk ?? question).trim();
    if (!q) return;

    setLoading(true);
    setError(null);
    setHighlightedSourceId(null);

    try {
      const res = await askQuestion(q);
      setResponse(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'An unexpected error occurred.';
      setError(msg);
      setResponse(null);
    } finally {
      setLoading(false);
    }
  };

  const handleCitationClick = (sourceId: string) => {
    setHighlightedSourceId(sourceId);
    const element = document.getElementById(`evidence-${sourceId}`);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  const handleSelectCandidate = (candidateName: string, originalQuery?: string) => {
    const newQuery = replaceAmbiguousTerm(question, originalQuery, candidateName);
    setQuestion(newQuery);
    handleSubmit(newQuery);
  };

  const isRefused = response?.flags?.includes('refused');

  return (
    <div className="app-container">
      {/* Permanent Research Prototype Notice Banner */}
      <aside className="disclaimer-banner" role="note" aria-label="Medical Disclaimer">
        <span className="prototype-pill">Research prototype, not medical advice</span>
        <span className="disclaimer-text">
          PharmaGraph does not provide medical diagnoses or dosing instructions. Always consult a licensed clinician for treatment decisions.
        </span>
      </aside>

      <header className="app-header">
        <div className="header-brand">
          <h1>PharmaGraph</h1>
          <span className="tagline">Evidence-Grounded Pharmacogenomics Intelligence Core</span>
        </div>
      </header>

      <main className="main-content">
        {/* Search Input Section */}
        <section className="query-section" aria-label="Biomedical Question Input">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSubmit();
            }}
            className="query-form"
          >
            <label htmlFor="question-input" className="query-label">
              Enter Gene-Drug Pharmacogenomic Question:
            </label>
            <div className="input-group">
              <input
                id="question-input"
                type="text"
                className="query-input"
                placeholder="e.g. What is the relationship between CYP2C19 and clopidogrel?"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                disabled={loading}
                autoFocus
              />
              <button
                type="submit"
                className="btn-submit"
                disabled={loading || !question.trim()}
                aria-label="Submit Question"
              >
                {loading ? 'Searching...' : 'Ask'}
              </button>
            </div>
          </form>

          {/* Quick Demo Starters */}
          <div className="demo-starters" aria-label="Example Questions">
            <span className="starters-label">Try example:</span>
            <button
              type="button"
              className="starter-btn"
              onClick={() => {
                const q = 'What is the relationship between CYP2C19 and clopidogrel?';
                setQuestion(q);
                handleSubmit(q);
              }}
            >
              CYP2C19 &amp; clopidogrel
            </button>
            <button
              type="button"
              className="starter-btn"
              onClick={() => {
                const q = 'warfarin VKORC1';
                setQuestion(q);
                handleSubmit(q);
              }}
            >
              warfarin VKORC1
            </button>
            <button
              type="button"
              className="starter-btn"
              onClick={() => {
                const q = 'I have acute chest pain, what dose of clopidogrel should I take?';
                setQuestion(q);
                handleSubmit(q);
              }}
            >
              Chest Pain Advice (Safety Guard)
            </button>
          </div>
        </section>

        {/* Loading Spinner */}
        {loading && (
          <div className="loading-state" role="status" aria-live="polite">
            <div className="spinner" aria-hidden="true"></div>
            <p>Retrieving grounded pharmacogenomics evidence and building extractive summary...</p>
          </div>
        )}

        {/* Error Notification */}
        {error && (
          <div className="error-state" role="alert">
            <h4>Request Error</h4>
            <p>{error}</p>
          </div>
        )}

        {/* Response Container */}
        {response && !loading && (
          <div className="response-container">
            {/* Entity Resolution Chips & Ambiguity Picker */}
            <EntityChips
              entities={response.resolved_entities}
              onSelectCandidate={handleSelectCandidate}
            />

            {isRefused ? (
              /* Refusal path: rendered in distinct panel with NO evidence area */
              <RefusalPanel answer={response.answer} flags={response.flags} />
            ) : (
              /* Success path: Visibly separated Answer and Evidence panels */
              <div className="content-split-layout">
                <div className="layout-col-answer">
                  <AnswerPanel
                    answer={response.answer}
                    claims={response.claims}
                    relatedClaims={response.related_claims ?? []}
                    answerMode={response.answer_mode}
                    flags={response.flags}
                    removedClaimsCount={response.removed_claims_count}
                    onCitationClick={handleCitationClick}
                  />
                </div>

                <div className="layout-col-evidence">
                  <EvidencePanel
                    bundle={response.evidence_bundle}
                    highlightedSourceId={highlightedSourceId}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      <footer className="app-footer">
        <p className="footer-disclaimer">
          <strong>Disclaimer:</strong>{' '}
          {response?.disclaimer_text ??
            'PharmaGraph is an experimental research system for pharmacogenomics intelligence and does NOT provide medical advice, clinical diagnosis, or dosing recommendations. Always consult a licensed physician, clinical geneticist, or pharmacist for medical decisions.'}
        </p>
        <p className="footer-meta">
          PharmaGraph Phase D3 &bull; Grounded Knowledge Graph + Multi-Path RRF Retrieval &bull; Built with React &amp; TypeScript
        </p>
      </footer>
    </div>
  );
};

export default App;

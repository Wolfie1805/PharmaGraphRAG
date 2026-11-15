import React, { useEffect, useRef, useState } from 'react';
import { askQuestion, fetchSiteStats } from './api';
import { AskResponse, MeaningCoverageStats, ResolvedEntity, SiteStats } from './types';
import { SearchBar } from './components/app/SearchBar';
import { ExampleGroups } from './components/app/ExampleGroups';
import { AtAGlanceCard } from './components/app/AtAGlanceCard';
import { SummaryCard } from './components/app/SummaryCard';
import { EvidenceChart } from './components/app/EvidenceChart';
import { EvidenceList } from './components/app/EvidenceList';
import {
  AmbiguityPickerCard,
  BackendOfflineCard,
  EmptyWelcomeCard,
  InsufficientEvidenceCard,
  RefusalCard,
  SkeletonLoading,
  UnrecognizedEntityCard,
} from './components/app/EdgeStates';

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

interface AppProps {
  initialQuestion?: string;
  initialStats?: MeaningCoverageStats;
}

export const App: React.FC<AppProps> = ({ initialQuestion = '', initialStats }) => {
  const [question, setQuestion] = useState<string>(initialQuestion);
  const [loading, setLoading] = useState<boolean>(false);
  const [backendOffline, setBackendOffline] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [activeHints, setActiveHints] = useState<string[]>([]);
  const [highlightedSourceId, setHighlightedSourceId] = useState<string | null>(null);
  const [siteStats, setSiteStats] = useState<SiteStats | null>(null);
  const [reducedEffects, setReducedEffects] = useState<boolean>(() => {
    if (typeof window !== 'undefined' && window.matchMedia) {
      return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }
    return false;
  });

  const searchInputRef = useRef<HTMLInputElement>(null);

  // Sync initial question if changed via URL hash
  useEffect(() => {
    if (initialQuestion !== undefined && initialQuestion !== '') {
      setQuestion(initialQuestion);
    }
  }, [initialQuestion]);

  // Fetch site snapshot metadata
  useEffect(() => {
    const metaEnv = (import.meta as unknown as { env?: { MODE?: string } }).env;
    if (metaEnv?.MODE === 'test') return;

    let active = true;
    fetchSiteStats().then((data) => {
      if (active && data) {
        setSiteStats(data);
      }
    });
    return () => {
      active = false;
    };
  }, [initialStats]);

  const handleQuery = async (queryText?: string, hints?: string[]) => {
    const q = (queryText !== undefined ? queryText : question).trim();
    if (!q) return;

    setLoading(true);
    setBackendOffline(false);
    setErrorMessage(null);
    setHighlightedSourceId(null);
    const hintsToUse = hints !== undefined ? hints : activeHints;

    try {
      const res = await askQuestion({
        question: q,
        entity_hints: hintsToUse.length > 0 ? hintsToUse : undefined,
      });
      setResponse(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'An unexpected error occurred.';
      if (msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('Load failed')) {
        setBackendOffline(true);
      } else {
        setErrorMessage(msg);
      }
      setResponse(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectAmbiguityCandidate = (candidateId: string, candidateName: string, originalTerm?: string) => {
    // When user selects a candidate from the ambiguity picker, re-query with that candidate's canonical_id in entity_hints
    const updatedHints = [candidateId];
    setActiveHints(updatedHints);
    const newQuery = replaceAmbiguousTerm(question, originalTerm, candidateName);
    setQuestion(newQuery);
    handleQuery(newQuery, updatedHints);
  };

  const handleSelectExample = (exampleQuery: string, hints?: string[]) => {
    setQuestion(exampleQuery);
    if (hints && hints.length > 0) {
      setActiveHints(hints);
      handleQuery(exampleQuery, hints);
    } else {
      setActiveHints([]);
      handleQuery(exampleQuery, []);
    }
  };

  const handleCitationClick = (sourceId: string) => {
    setHighlightedSourceId(sourceId);
    const el = document.getElementById(`evidence-${sourceId}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  const handleClear = () => {
    setQuestion('');
    setActiveHints([]);
    setResponse(null);
    setErrorMessage(null);
    setBackendOffline(false);
  };

  // Inspect response state
  const isRefused = response?.flags?.includes('refused');
  const ambiguousEntities = (response?.resolved_entities || []).filter(
    (e) => e.status === 'ambiguous' && e.candidates && e.candidates.length > 1
  );
  const ungroundedEntities = (response?.resolved_entities || []).filter(
    (e) => e.status === 'unresolved'
  );
  const hasSufficientEvidence = response?.evidence_bundle?.has_sufficient_evidence ?? true;
  const evidenceItems = response?.evidence_bundle?.items || [];
  const snapshotDate = siteStats?.generated_at
    ? siteStats.generated_at.split('T')[0]
    : '2026-11-14';

  return (
    <div className={`app-workspace ${reducedEffects ? 'effects-reduced' : ''}`}>
      {/* 2-Column Responsive Layout */}
      <div className="workspace-layout">
        {/* LEFT COLUMN: Sidebar (320px - 360px on desktop; collapses to top bar on <=768px) */}
        <aside className="workspace-sidebar" aria-label="Query Controls and Navigation">
          <div className="sidebar-top-nav">
            <a href="#/" className="btn-back-overview">
              <span className="back-arrow" aria-hidden="true">&larr;</span> Back to Overview
            </a>
          </div>

          <div className="sidebar-heading-block">
            <h1 className="sidebar-main-heading">Ask about a gene and a medicine</h1>
            <p className="sidebar-subheading">
              Grounded retrieval from CPIC, PharmGKB, ClinPGx &amp; PubMed.
            </p>
          </div>

          {/* Search bar with Combobox Autocomplete */}
          <div className="sidebar-search-block">
            <SearchBar
              inputRef={searchInputRef}
              value={question}
              onChange={setQuestion}
              onSubmit={(q, hints) => {
                if (hints) setActiveHints(hints);
                handleQuery(q, hints);
              }}
              onClear={handleClear}
              loading={loading}
            />
          </div>

          {/* Example Groups Tabs */}
          <div className="sidebar-examples-block">
            <ExampleGroups
              disabled={loading}
              onSelectQuestion={handleSelectExample}
            />
          </div>

          {/* Sidebar Footer Controls */}
          <div className="sidebar-footer">
            {initialStats && Object.keys(initialStats.per_source_type).length > 0 && (
              <section className="coverage-stats-panel" aria-label="Meaning Search Coverage Stats">
                <div className="coverage-stats-header">
                  <span className="coverage-stats-title">Meaning Search Coverage by Source Type</span>
                  <span className={`coverage-badge ${initialStats.is_partial ? 'partial' : 'complete'}`}>
                    {initialStats.is_partial ? 'Partial Index' : 'Full Index'}
                  </span>
                </div>
                <div className="coverage-stats-grid">
                  {Object.entries(initialStats.per_source_type).map(([sourceType, info]) => (
                    <div key={sourceType} className="coverage-stat-item">
                      <span className="coverage-type">{sourceType}</span>
                      <span className="coverage-counts">
                        {info.indexed.toLocaleString()} / {info.expected.toLocaleString()}
                      </span>
                      <span className="coverage-state">
                        {info.complete ? 'complete' : info.indexed > 0 ? 'partial' : 'unindexed'}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <div className="sidebar-disclaimer-pill" role="note">
              Research prototype, not medical advice
            </div>

            <div className="sidebar-toggles-row">
              <label className="toggle-label" htmlFor="toggle-reduced-motion">
                <input
                  id="toggle-reduced-motion"
                  type="checkbox"
                  checked={reducedEffects}
                  onChange={(e) => setReducedEffects(e.target.checked)}
                />
                <span>Reduce effects</span>
              </label>
            </div>

            <div className="sidebar-snapshot-meta">
              Data snapshot generated on {snapshotDate}
            </div>
          </div>
        </aside>

        {/* RIGHT COLUMN: Main Content Area */}
        <main className="workspace-main" id="main-content" aria-live="polite">
          {/* 1. Loading Skeleton */}
          {loading && <SkeletonLoading reducedEffects={reducedEffects} />}

          {/* 2. Backend Offline State */}
          {!loading && backendOffline && (
            <BackendOfflineCard onRetry={() => handleQuery()} />
          )}

          {/* 3. Generic Error State */}
          {!loading && !backendOffline && errorMessage && (
            <div className="edge-card card-error" role="alert">
              <h4 className="edge-card-title">Query Processing Notice</h4>
              <p className="edge-body-text">{errorMessage}</p>
            </div>
          )}

          {/* 4. Empty State (No query yet) */}
          {!loading && !backendOffline && !errorMessage && !response && (
            <EmptyWelcomeCard
              onSelectStarter={(starter) => {
                setQuestion(starter);
                handleQuery(starter);
              }}
            />
          )}

          {/* 5. Response Results */}
          {!loading && !backendOffline && !errorMessage && response && (
            <div className="response-results-wrapper">
              {/* Clinical Refusal Edge State: NO evidence area rendered */}
              {isRefused ? (
                <RefusalCard answer={response.answer} flags={response.flags} />
              ) : (
                <>
                  {/* Ambiguity Picker Edge State */}
                  {ambiguousEntities.length > 0 && (
                    <div className="ambiguity-section-wrapper">
                      {ambiguousEntities.map((ambEntity: ResolvedEntity) => (
                        <AmbiguityPickerCard
                          key={ambEntity.canonical_id || ambEntity.name}
                          ambiguousEntity={ambEntity}
                          onSelectCandidate={handleSelectAmbiguityCandidate}
                        />
                      ))}
                    </div>
                  )}

                  {/* Unrecognized Entity Notice */}
                  {ungroundedEntities.length > 0 && (
                    <div className="unrecognized-section-wrapper">
                      {ungroundedEntities.map((unEnt) => (
                        <UnrecognizedEntityCard
                          key={unEnt.query}
                          term={unEnt.query}
                          onSelectSuggestion={(corrected) => {
                            setQuestion(corrected);
                            handleQuery(corrected);
                          }}
                        />
                      ))}
                    </div>
                  )}

                  {/* Insufficient Evidence Notice */}
                  {!hasSufficientEvidence && <InsufficientEvidenceCard />}

                  {/* At A Glance Card */}
                  <AtAGlanceCard
                    resolvedEntities={response.resolved_entities || []}
                    evidenceBundle={response.evidence_bundle}
                  />

                  {/* Summary Card */}
                  <SummaryCard
                    answer={response.answer}
                    claims={response.claims || []}
                    flags={response.flags || []}
                    answerMode={response.answer_mode}
                    onCitationClick={handleCitationClick}
                  />

                  {/* SVG Evidence Chart */}
                  <EvidenceChart items={evidenceItems} />

                  {/* Evidence Cards List */}
                  <EvidenceList
                    items={evidenceItems}
                    highlightedSourceId={highlightedSourceId}
                  />
                </>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default App;

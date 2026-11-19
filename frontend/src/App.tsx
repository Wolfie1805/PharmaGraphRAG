import React, { useCallback, useEffect, useRef, useState } from 'react';
import { askQuestion, fetchSiteStats } from './api';
import { AskResponse, MeaningCoverageStats, ResolvedEntity, SiteStats } from './types';
import { SearchBar } from './components/app/SearchBar';
import { HomeStateCards } from './components/app/HomeStateCards';
import { ResultsHeader } from './components/app/ResultsHeader';
import { OverviewTable } from './components/app/OverviewTable';
import { DetailSectionsView } from './components/app/DetailSectionsView';
import { BrandLookupView } from './components/app/BrandLookupView';
import {
  AmbiguityPickerCard,
  BackendOfflineCard,
  HowToReadThisCard,
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
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
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
  const questionRef = useRef(question);
  questionRef.current = question;
  const activeHintsRef = useRef(activeHints);
  activeHintsRef.current = activeHints;

  const handleQuery = useCallback(
    async (
      queryText?: string,
      hints?: string[],
      isPaging = false,
      offset = 0
    ) => {
      const q = (queryText !== undefined ? queryText : questionRef.current).trim();
      if (!q) return;

      if (isPaging) {
        setLoadingMore(true);
      } else {
        setLoading(true);
        setBackendOffline(false);
        setErrorMessage(null);
        setHighlightedSourceId(null);
      }

      const hintsToUse = hints !== undefined ? hints : activeHintsRef.current;

      try {
        const res = await askQuestion({
          question: q,
          entity_hints: hintsToUse && hintsToUse.length > 0 ? hintsToUse : undefined,
          overview_offset: isPaging ? offset : 0,
          overview_limit: 20,
        });

        if (isPaging) {
          setResponse((prev) => {
            if (prev?.overview && res.overview) {
              return {
                ...prev,
                overview: {
                  ...res.overview,
                  rows: [...prev.overview.rows, ...res.overview.rows],
                },
              };
            }
            return res;
          });
        } else {
          setResponse(res);
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'An unexpected error occurred.';
        if (
          msg.includes('Failed to fetch') ||
          msg.includes('NetworkError') ||
          msg.includes('Load failed') ||
          msg.includes('ConnectionRefused')
        ) {
          setBackendOffline(true);
        } else {
          setErrorMessage(msg);
        }
        if (!isPaging) {
          setResponse(null);
        }
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    []
  );

  // Sync initial question if changed via URL hash
  useEffect(() => {
    if (initialQuestion !== undefined && initialQuestion !== '') {
      setQuestion(initialQuestion);
      handleQuery(initialQuestion, []);
    }
  }, [initialQuestion, handleQuery]);

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

  const handleSelectAmbiguityCandidate = (
    candidateId: string,
    candidateName: string,
    originalTerm?: string
  ) => {
    const isBrand = candidateId.startsWith('brand:');
    const updatedHints = isBrand ? [] : [candidateId];
    setActiveHints(updatedHints);
    const newQuery = replaceAmbiguousTerm(question, originalTerm, candidateName);
    setQuestion(newQuery);
    handleQuery(newQuery, updatedHints);
  };

  const handleSelectExample = (exampleQuery: string, hints?: string[]) => {
    setQuestion(exampleQuery);
    const h = hints || [];
    setActiveHints(h);
    handleQuery(exampleQuery, h);
  };

  const handleOpenPair = (pairQuery: string, hints: string[]) => {
    setQuestion(pairQuery);
    setActiveHints(hints);
    handleQuery(pairQuery, hints);
  };

  const handleLoadMoreOverview = () => {
    if (!response?.overview) return;
    const currentLength = response.overview.rows.length;
    handleQuery(question, activeHints, true, currentLength);
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

  const snapshotDate = siteStats?.generated_at
    ? siteStats.generated_at.split('T')[0]
    : '2026-11-14';

  const queryMode = response?.query_mode || 'unrecognized';
  const isRefusal = queryMode === 'refused' || (response?.flags || []).includes('refused');
  const isAmbiguous =
    queryMode === 'ambiguous' ||
    (response?.resolved_entities || []).some((e) => e.status === 'ambiguous');
  const isBrandLookup = queryMode === 'brand_lookup' && Boolean(response?.brands);
  const isUnrecognized =
    !isBrandLookup &&
    (queryMode === 'unrecognized' ||
      (response?.flags || []).includes('unrecognized_entity'));
  const isOverview =
    queryMode === 'medicine_overview' ||
    queryMode === 'gene_overview' ||
    queryMode === 'variant_overview';
  const isDetail = queryMode === 'pair_detail' || queryMode === 'variant_detail';
  const hasInsufficientEvidence = (response?.flags || []).includes('insufficient_evidence');

  return (
    <div className={`app-workspace ${reducedEffects ? 'effects-reduced' : ''}`}>
      {/* 2-Column Responsive Layout */}
      <div className="workspace-layout">
        {/* LEFT COLUMN: Sidebar */}
        <aside className="workspace-sidebar" aria-label="Query Controls and Navigation">
          <div className="sidebar-top-nav">
            <a href="#/" className="btn-back-overview">
              <span className="back-arrow" aria-hidden="true">&larr;</span> Back to Overview
            </a>
          </div>

          <div className="sidebar-heading-block">
            <h1 className="sidebar-main-heading">Biomedical Evidence Search</h1>
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

          {/* Persistent "How to read this" Drawer */}
          <div className="sidebar-how-to-read">
            <HowToReadThisCard />
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
          {/* Persistent Disclaimer Banner */}
          <div className="disclaimer-banner" role="note">
            <span className="banner-prefix">Research prototype:</span> All evidence is directly extracted from ClinPGx, PharmGKB, CPIC, and PubMed archives. Not intended for direct medical decision making.
          </div>

          {/* 1. Loading Skeleton */}
          {loading && !loadingMore && <SkeletonLoading reducedEffects={reducedEffects} />}

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

          {/* 4. Home State (Empty/Idle Query) */}
          {!loading && !backendOffline && !errorMessage && !response && (
            <HomeStateCards
              onSelectExample={handleSelectExample}
              disabled={loading}
            />
          )}

          {/* 5. Response Results */}
          {!loading && !backendOffline && !errorMessage && response && (
            <div className="response-results-wrapper">
              {/* Results Header (You asked, We understood, Showing, Try next) */}
              <ResultsHeader
                question={response.question}
                queryMode={queryMode}
                resolvedEntities={response.resolved_entities || []}
                suggestedNext={response.suggested_next || []}
                onSelectSuggestion={(nextQ, hints) => handleSelectExample(nextQ, hints)}
              />

              {/* Edge State A: Clinical Refusal */}
              {isRefusal && (
                <RefusalCard
                  answer={response.answer}
                  flags={response.flags}
                  templates={response.prompt_templates}
                  onSelectTemplate={(ex) => handleSelectExample(ex)}
                />
              )}

              {/* Edge State B: Ambiguous Entity */}
              {!isRefusal && isAmbiguous && (
                <div className="ambiguity-section-wrapper">
                  {(response.resolved_entities || [])
                    .filter((e) => e.status === 'ambiguous' && e.candidates && e.candidates.length > 0)
                    .map((ambEntity: ResolvedEntity) => (
                      <AmbiguityPickerCard
                        key={ambEntity.canonical_id || ambEntity.name}
                        ambiguousEntity={ambEntity}
                        onSelectCandidate={handleSelectAmbiguityCandidate}
                      />
                    ))}
                </div>
              )}

              {/* Edge State C: Unrecognized Entity */}
              {!isRefusal && !isAmbiguous && !isBrandLookup && isUnrecognized && (
                <UnrecognizedEntityCard
                  term={response.question}
                  templates={response.prompt_templates}
                  onSelectTemplate={(ex) => handleSelectExample(ex)}
                />
              )}

              {/* Mode 0: Brand Lookup Mode (NRCeS Indian Brand Names) */}
              {!isRefusal && !isAmbiguous && isBrandLookup && response.brands && (
                <BrandLookupView
                  brands={response.brands}
                  onOpenIngredient={(displayName, canonicalId) => {
                    handleSelectExample(displayName, [canonicalId]);
                  }}
                  onPageChange={(newOffset) => {
                    handleQuery(question, activeHints, false, newOffset);
                  }}
                />
              )}

              {/* Mode 1: Overview Mode (Medicine or Gene Overview) */}
              {!isRefusal && !isAmbiguous && !isBrandLookup && !isUnrecognized && isOverview && response.overview && (
                <OverviewTable
                  overview={response.overview}
                  queryMode={queryMode}
                  onOpenPair={handleOpenPair}
                  onLoadMore={handleLoadMoreOverview}
                  loadingMore={loadingMore}
                />
              )}

              {/* Mode 2: Detail Mode (Pair Detail or Variant Detail) */}
              {!isRefusal && !isAmbiguous && !isBrandLookup && !isUnrecognized && isDetail && (
                <>
                  {hasInsufficientEvidence && (
                    <InsufficientEvidenceCard
                      totalItems={response.evidence_bundle?.total_items || 0}
                    />
                  )}

                  {response.sections && (
                    <DetailSectionsView
                      sections={response.sections}
                      claims={response.claims || []}
                      answer={response.answer}
                      highlightedSourceId={highlightedSourceId}
                      onCitationClick={handleCitationClick}
                    />
                  )}
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

import React, { useEffect, useRef, useState } from 'react';
import { fetchSuggestions } from '../../api';
import { ReadyMadeSearch, SuggestItem } from '../../types';

interface SearchBarProps {
  value: string;
  onChange: (val: string) => void;
  onSubmit: (q?: string, hints?: string[]) => void;
  loading: boolean;
  onClear: () => void;
  placeholder?: string;
  inputRef?: React.RefObject<HTMLInputElement>;
}

export const SearchBar: React.FC<SearchBarProps> = ({
  value,
  onChange,
  onSubmit,
  loading,
  onClear,
  placeholder = 'Search a gene, variant, or medicine (e.g. CYP2C19 clopidogrel)',
  inputRef: externalInputRef,
}) => {
  const internalInputRef = useRef<HTMLInputElement>(null);
  const inputRef = externalInputRef || internalInputRef;

  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [suggestions, setSuggestions] = useState<SuggestItem[]>([]);
  const [searches, setSearches] = useState<ReadyMadeSearch[]>([]);
  const [activeIndex, setActiveIndex] = useState<number>(-1);
  const [fetchingSuggestions, setFetchingSuggestions] = useState<boolean>(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Debounced suggest fetch
  useEffect(() => {
    const metaEnv = (import.meta as unknown as { env?: { MODE?: string } }).env;
    if (metaEnv?.MODE === 'test') return;

    const trimmed = value.trim();
    if (trimmed.length < 2) {
      setSuggestions([]);
      setSearches([]);
      setIsOpen(false);
      setActiveIndex(-1);
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const timer = setTimeout(async () => {
      setFetchingSuggestions(true);
      try {
        const res = await fetchSuggestions(trimmed, 8, controller.signal);
        if (!controller.signal.aborted) {
          setSuggestions(res.suggestions || []);
          setSearches(res.searches || []);
          setIsOpen((res.suggestions?.length > 0 || res.searches?.length > 0));
          setActiveIndex(-1);
        }
      } catch {
        if (!controller.signal.aborted) {
          setSuggestions([]);
          setSearches([]);
        }
      } finally {
        if (!controller.signal.aborted) {
          setFetchingSuggestions(false);
        }
      }
    }, 150);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [value]);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const standardSuggestions = suggestions.filter(
    (item) => item.sort_group !== 'Indian brand names (NRCeS)' && item.entity_type !== 'brand'
  );
  const brandSuggestions = suggestions.filter(
    (item) => item.sort_group === 'Indian brand names (NRCeS)' || item.entity_type === 'brand'
  );
  const totalItems = suggestions.length + searches.length;

  const getItemAt = (index: number): { type: 'suggestion'; item: SuggestItem } | { type: 'search'; item: ReadyMadeSearch } | null => {
    if (index < 0 || index >= totalItems) return null;
    if (index < standardSuggestions.length) {
      return { type: 'suggestion', item: standardSuggestions[index] };
    }
    if (index < suggestions.length) {
      return { type: 'suggestion', item: brandSuggestions[index - standardSuggestions.length] };
    }
    return { type: 'search', item: searches[index - suggestions.length] };
  };

  const handleSelectSuggestion = (item: SuggestItem) => {
    onChange(item.display_label);
    setIsOpen(false);
    setActiveIndex(-1);
    if (item.sort_group === 'Indian brand names (NRCeS)' || item.entity_type === 'brand') {
      onSubmit(item.display_label);
    } else {
      onSubmit(item.display_label, [item.canonical_id]);
    }
  };

  const handleSelectSearch = (search: ReadyMadeSearch) => {
    onChange(search.query);
    setIsOpen(false);
    setActiveIndex(-1);
    onSubmit(search.query);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!isOpen && totalItems > 0) {
        setIsOpen(true);
        setActiveIndex(0);
      } else if (totalItems > 0) {
        setActiveIndex((prev) => (prev + 1) % totalItems);
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (totalItems > 0) {
        setActiveIndex((prev) => (prev <= 0 ? totalItems - 1 : prev - 1));
      }
    } else if (e.key === 'Enter') {
      if (isOpen && activeIndex >= 0) {
        e.preventDefault();
        const selected = getItemAt(activeIndex);
        if (selected?.type === 'suggestion') {
          handleSelectSuggestion(selected.item);
        } else if (selected?.type === 'search') {
          handleSelectSearch(selected.item);
        }
      } else {
        setIsOpen(false);
        onSubmit();
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false);
      setActiveIndex(-1);
    }
  };

  const activeDescendantId = activeIndex >= 0 ? `suggest-option-${activeIndex}` : undefined;

  return (
    <div className="search-bar-container" ref={containerRef}>
      <label
        htmlFor="question-input"
        className="query-label"
        style={{
          position: 'absolute',
          width: '1px',
          height: '1px',
          padding: 0,
          margin: '-1px',
          overflow: 'hidden',
          clip: 'rect(0, 0, 0, 0)',
          whiteSpace: 'nowrap',
          borderWidth: 0,
        }}
      >
        Enter Gene-Drug Pharmacogenomic Question:
      </label>
      <div className="search-input-wrapper">
        <span className="search-icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </span>

        <input
          id="question-input"
          ref={inputRef}
          type="text"
          className="search-input-pill"
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            if (totalItems > 0) setIsOpen(true);
          }}
          role="combobox"
          aria-expanded={isOpen}
          aria-autocomplete="list"
          aria-controls="suggest-listbox"
          aria-activedescendant={activeDescendantId}
          aria-label="Enter Gene-Drug Pharmacogenomic Question"
          autoFocus
        />

        {value.trim().length > 0 && (
          <button
            type="button"
            className="search-clear-btn"
            onClick={() => {
              onClear();
              setIsOpen(false);
              inputRef.current?.focus();
            }}
            aria-label="Clear search input"
          >
            ✕
          </button>
        )}

        {(loading || fetchingSuggestions) && (
          <span className="search-spinner-inline" aria-label="Loading suggestions">
            <span className="spinner-dot" />
          </span>
        )}

        <button
          type="button"
          className="search-submit-btn"
          disabled={loading || !value.trim()}
          onClick={() => {
            setIsOpen(false);
            onSubmit();
          }}
          aria-label="Submit Question"
        >
          {loading ? 'Searching' : 'Search'}
        </button>
      </div>

      {isOpen && totalItems > 0 && (
        <div
          id="suggest-listbox"
          className="suggest-dropdown-menu"
          role="listbox"
          aria-label="Suggestions"
        >
          {standardSuggestions.length > 0 && (
            <div className="suggest-group" role="group" aria-label="Genes and medicines">
              <div className="suggest-group-header">Genes &amp; Medicines</div>
              {standardSuggestions.map((item, localIdx) => {
                const idx = localIdx;
                const isSelected = activeIndex === idx;
                const isTypo = item.match_kind === 'typo';
                return (
                  <div
                    key={`${item.canonical_id}-${item.matched_alias}-${idx}`}
                    id={`suggest-option-${idx}`}
                    className={`suggest-option-item ${isSelected ? 'is-active' : ''}`}
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => handleSelectSuggestion(item)}
                    onMouseEnter={() => setActiveIndex(idx)}
                  >
                    <div className="suggest-item-primary">
                      <span className="suggest-item-name">{item.display_label}</span>
                      <span className={`suggest-tag tag-${item.sort_group || item.entity_type}`}>
                        {item.sort_group || item.entity_type}
                      </span>
                      {isTypo && <span className="suggest-tag tag-typo">Did you mean</span>}
                      {item.is_ambiguous && (
                        <span className="suggest-tag tag-ambiguous">
                          Ambiguous ({item.candidate_count ?? 2})
                        </span>
                      )}
                    </div>
                    {item.matched_alias && item.matched_alias.toLowerCase() !== item.display_label.toLowerCase() && (
                      <div className="suggest-item-secondary">
                        <span className="suggest-alias-prefix">Matched alias:</span>{' '}
                        <span className="suggest-alias-val">{item.matched_alias}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {brandSuggestions.length > 0 && (
            <div className="suggest-group" role="group" aria-label="Indian brand names (NRCeS)">
              <div className="suggest-group-header">Indian brand names (NRCeS)</div>
              {brandSuggestions.map((item, localIdx) => {
                const idx = standardSuggestions.length + localIdx;
                const isSelected = activeIndex === idx;
                const isTypo = item.match_kind === 'typo';
                return (
                  <div
                    key={`${item.canonical_id}-${item.matched_alias}-${idx}`}
                    id={`suggest-option-${idx}`}
                    className={`suggest-option-item ${isSelected ? 'is-active' : ''}`}
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => handleSelectSuggestion(item)}
                    onMouseEnter={() => setActiveIndex(idx)}
                  >
                    <div className="suggest-item-primary">
                      <span className="suggest-item-name">{item.display_label}</span>
                      <span className="suggest-tag tag-brand">
                        Indian brand (NRCeS)
                      </span>
                      {isTypo && <span className="suggest-tag tag-typo">Did you mean</span>}
                    </div>
                    {item.matched_alias && item.matched_alias.toLowerCase() !== item.display_label.toLowerCase() && (
                      <div className="suggest-item-secondary">
                        <span className="suggest-alias-prefix">Matched alias:</span>{' '}
                        <span className="suggest-alias-val">{item.matched_alias}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {searches.length > 0 && (
            <div className="suggest-group" role="group" aria-label="Ready-made searches">
              <div className="suggest-group-header">Ready-made Searches</div>
              {searches.map((search, sIdx) => {
                const overallIdx = suggestions.length + sIdx;
                const isSelected = activeIndex === overallIdx;
                return (
                  <div
                    key={`${search.query}-${sIdx}`}
                    id={`suggest-option-${overallIdx}`}
                    className={`suggest-option-item is-search ${isSelected ? 'is-active' : ''}`}
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => handleSelectSearch(search)}
                    onMouseEnter={() => setActiveIndex(overallIdx)}
                  >
                    <div className="suggest-item-primary">
                      <span className="suggest-search-icon" aria-hidden="true">↳</span>
                      <span className="suggest-search-query">{search.gene} + {search.chemical}</span>
                      <span className="suggest-tag tag-search">Pair</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

import { AskResponse, DemoQuestion, MeaningCoverageStats, SiteStats, SuggestResponse } from './types';

const API_BASE = 'http://localhost:8000/api';

export async function fetchSiteStats(): Promise<SiteStats | null> {
  try {
    const response = await fetch('/site_stats.json');
    if (!response.ok) return null;
    return (await response.json()) as SiteStats;
  } catch {
    return null;
  }
}

export async function fetchDemoQuestions(): Promise<DemoQuestion[]> {
  try {
    const response = await fetch('/demo_questions.json');
    if (!response.ok) return [];
    return (await response.json()) as DemoQuestion[];
  } catch {
    return [];
  }
}

export async function fetchStats(): Promise<MeaningCoverageStats | null> {
  try {
    const response = await fetch(`${API_BASE}/stats`);
    if (!response.ok) return null;
    const data = await response.json();
    if (data && typeof data.per_source_type === 'object') {
      return data as MeaningCoverageStats;
    }
    return null;
  } catch {
    return null;
  }
}

export async function fetchSuggestions(
  q: string,
  limit = 8,
  signal?: AbortSignal
): Promise<SuggestResponse> {
  const trimmed = q.trim();
  if (trimmed.length < 2) {
    return { suggestions: [], searches: [] };
  }
  try {
    const params = new URLSearchParams({ q: trimmed, limit: String(limit) });
    const response = await fetch(`${API_BASE}/suggest?${params.toString()}`, { signal });
    if (!response.ok) return { suggestions: [], searches: [] };
    return (await response.json()) as SuggestResponse;
  } catch {
    return { suggestions: [], searches: [] };
  }
}

export interface AskOptions {
  question: string;
  answer_mode?: string;
  entity_hints?: string[];
  overview_offset?: number;
  overview_limit?: number;
}

export async function askQuestion(
  questionOrOptions: string | AskOptions,
  signal?: AbortSignal
): Promise<AskResponse> {
  const payload =
    typeof questionOrOptions === 'string'
      ? { question: questionOrOptions }
      : questionOrOptions;

  const response = await fetch(`${API_BASE}/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status} ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson && errJson.detail) {
        errorDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

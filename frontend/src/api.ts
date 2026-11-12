import { AskResponse, MeaningCoverageStats } from './types';

const API_BASE = 'http://localhost:8000/api';

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

export async function askQuestion(question: string): Promise<AskResponse> {
  const response = await fetch(`${API_BASE}/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ question }),
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

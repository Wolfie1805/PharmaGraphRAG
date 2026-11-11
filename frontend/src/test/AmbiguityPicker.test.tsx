import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { EntityChips } from '../components/EntityChips';
import { App } from '../App';
import { ResolvedEntity } from '../types';

const resolvedEntity: ResolvedEntity = {
  name: 'CYP2C19',
  query: 'CYP2C19',
  status: 'resolved',
  canonical_id: 'pg:gene:1559',
};

const ambiguousEntity: ResolvedEntity = {
  name: 'DBI',
  query: 'DBI',
  status: 'ambiguous',
  candidates: [
    {
      canonical_id: 'PA123',
      entity_type: 'gene',
      primary_source_id: 'PA123',
      display_name: 'DBI gene',
      normalized_name: 'dbi',
      is_drug: false,
      gene_symbol: 'DBI',
      defined_by: 'primary_definition',
      is_ambiguous: true,
    },
    {
      canonical_id: 'PA456',
      entity_type: 'chemical',
      primary_source_id: 'PA456',
      display_name: 'diazepam',
      normalized_name: 'diazepam',
      is_drug: true,
      gene_symbol: null,
      defined_by: 'primary_definition',
      is_ambiguous: true,
    },
  ],
};

describe('EntityChips ambiguity picker', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders a resolved entity chip with Resolved badge', () => {
    render(<EntityChips entities={[resolvedEntity]} onSelectCandidate={vi.fn()} />);
    expect(screen.getByText('CYP2C19')).toBeInTheDocument();
    expect(screen.getByText('Resolved')).toBeInTheDocument();
  });

  it('opens candidate picker dialog when ambiguity button is clicked', () => {
    render(<EntityChips entities={[ambiguousEntity]} onSelectCandidate={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /Resolve ambiguous entity DBI/i }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('DBI gene')).toBeInTheDocument();
    expect(screen.getByText('diazepam')).toBeInTheDocument();
  });

  it('calls onSelectCandidate with display_name and original query when chosen', () => {
    const onSelectCandidate = vi.fn();
    render(<EntityChips entities={[ambiguousEntity]} onSelectCandidate={onSelectCandidate} />);
    fireEvent.click(screen.getByRole('button', { name: /Resolve ambiguous entity DBI/i }));
    fireEvent.click(screen.getByText('DBI gene'));
    expect(onSelectCandidate).toHaveBeenCalledWith('DBI gene', 'DBI');
  });

  it('closes dialog on Escape key press', () => {
    render(<EntityChips entities={[ambiguousEntity]} onSelectCandidate={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /Resolve ambiguous entity DBI/i }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('re-asks backend with chosen candidate in App when ambiguous candidate is selected', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          question: 'What is DBI?',
          answer: 'Ambiguous entity DBI.',
          claims: [],
          evidence_bundle: {
            query: 'What is DBI?',
            items: [],
            total_items: 0,
            has_sufficient_evidence: false,
            conflicts_detected: false,
          },
          resolved_entities: [ambiguousEntity],
          flags: ['ambiguous_entity', 'insufficient_evidence'],
          removed_claims_count: 0,
          disclaimer_text: 'Research prototype, not medical advice',
          answer_mode: 'extractive',
          llm_calls: 0,
          network_calls: 0,
          builder_calls: 0,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          question: 'What is diazepam?',
          answer: 'Resolved answer for diazepam.',
          claims: [],
          evidence_bundle: {
            query: 'What is diazepam?',
            items: [],
            total_items: 0,
            has_sufficient_evidence: false,
            conflicts_detected: false,
          },
          resolved_entities: [
            { name: 'diazepam', query: 'diazepam', status: 'resolved', canonical_id: 'PA456' },
          ],
          flags: [],
          removed_claims_count: 0,
          disclaimer_text: 'Research prototype, not medical advice',
          answer_mode: 'extractive',
          llm_calls: 0,
          network_calls: 0,
          builder_calls: 1,
        }),
      });

    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    const input = screen.getByLabelText(/Enter Gene-Drug Pharmacogenomic Question/i);
    fireEvent.change(input, { target: { value: 'What is DBI?' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit Question/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Resolve ambiguous entity DBI/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Resolve ambiguous entity DBI/i }));
    fireEvent.click(screen.getByText('diazepam'));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });

    const secondCallBody = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(secondCallBody.question).toBe('What is diazepam?');
  });
});

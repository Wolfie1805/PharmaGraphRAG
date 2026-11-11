import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AnswerPanel } from '../components/AnswerPanel';
import { App } from '../App';

describe('AnswerPanel citation highlighting', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('calls onCitationClick with the source ID when a claim citation pill is clicked', () => {
    const onCitationClick = vi.fn();
    render(
      <AnswerPanel
        answer="Test answer about CYP2C19 *2/*3 alleles."
        claims={[{ text: 'Claim about CYP2C19 *2/*3', source_ids: ['1183681642'] }]}
        answerMode="extractive"
        flags={[]}
        removedClaimsCount={0}
        onCitationClick={onCitationClick}
      />
    );
    const pill = screen.getByRole('button', { name: /^Citation 1183681642$/i });
    fireEvent.click(pill);
    expect(onCitationClick).toHaveBeenCalledWith('1183681642');
    // Star alleles render literally without markdown emphasis stripping asterisks
    expect(screen.getByText(/CYP2C19 \*2\/\*3 alleles/)).toBeInTheDocument();
  });

  it('makes inline citation IDs inside the answer text clickable', () => {
    const onCitationClick = vi.fn();
    render(
      <AnswerPanel
        answer="- [pubmed 19955249] Study on CYP2C19*2 and clopidogrel."
        claims={[{ text: 'CYP2C19*2 reduces active metabolite', source_ids: ['19955249'] }]}
        answerMode="extractive"
        flags={[]}
        removedClaimsCount={0}
        onCitationClick={onCitationClick}
      />
    );
    const inlineBtn = screen.getByRole('button', { name: /Jump to evidence 19955249/i });
    fireEvent.click(inlineBtn);
    expect(onCitationClick).toHaveBeenCalledWith('19955249');
  });

  it('highlights and scrolls to matching evidence card when citation marker is clicked in App', async () => {
    const scrollIntoViewMock = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoViewMock;

    const mockResponse = {
      question: 'CYP2C19 and clopidogrel',
      answer: '- [pubmed 19955249] Clopidogrel metabolism depends on CYP2C19.',
      claims: [{ text: 'Clopidogrel metabolism depends on CYP2C19.', source_ids: ['19955249'] }],
      evidence_bundle: {
        query: 'CYP2C19 and clopidogrel',
        total_items: 1,
        has_sufficient_evidence: true,
        conflicts_detected: false,
        items: [
          {
            source_id: '19955249',
            source_type: 'pubmed',
            title: 'CYP2C19 polymorphism and clopidogrel response',
            date: '2009-12',
            chunk_text: 'Carriers of CYP2C19 *2/*3 loss-of-function alleles exhibit reduced active metabolite.',
            entities: ['pg:gene:1559', 'pg:chem:449053'],
            matched_entities: ['pg:gene:1559', 'pg:chem:449053'],
            retrieval_paths: ['bm25', 'meaning'],
            score: 0.032,
          },
        ],
      },
      resolved_entities: [],
      flags: [],
      removed_claims_count: 0,
      disclaimer_text: 'Research prototype, not medical advice',
      answer_mode: 'extractive',
      llm_calls: 0,
      network_calls: 0,
      builder_calls: 1,
    };

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      })
    );

    render(<App />);
    const input = screen.getByLabelText(/Enter Gene-Drug Pharmacogenomic Question/i);
    fireEvent.change(input, { target: { value: 'CYP2C19 and clopidogrel' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit Question/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^Citation 19955249$/i })).toBeInTheDocument();
    });

    const card = document.getElementById('evidence-19955249');
    expect(card).not.toBeNull();
    expect(card?.className).not.toContain('card-highlighted');

    fireEvent.click(screen.getByRole('button', { name: /^Citation 19955249$/i }));

    expect(scrollIntoViewMock).toHaveBeenCalledTimes(1);
    expect(card?.className).toContain('card-highlighted');
  });

  it('shows "Extractive answer (no AI model)" for extractive mode', () => {
    render(
      <AnswerPanel
        answer="Test"
        claims={[]}
        answerMode="extractive"
        flags={[]}
        removedClaimsCount={0}
        onCitationClick={vi.fn()}
      />
    );
    expect(screen.getByText('Extractive answer (no AI model)')).toBeInTheDocument();
  });

  it('renders literal asterisks and script tags strictly as plain text', () => {
    const payload = '<img src=x onerror=alert(1)> CYP2C19 *1/*2 *17';
    render(
      <AnswerPanel
        answer={payload}
        claims={[]}
        answerMode="extractive"
        flags={[]}
        removedClaimsCount={0}
        onCitationClick={vi.fn()}
      />
    );
    expect(screen.getByText(payload)).toBeInTheDocument();
    expect(document.querySelector('img')).toBeNull();
  });
});

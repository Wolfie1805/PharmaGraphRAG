import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { EvidenceCard } from '../components/EvidenceCard';
import { EvidencePanel } from '../components/EvidencePanel';
import { RefusalPanel } from '../components/RefusalPanel';
import { App } from '../App';

describe('Evidence cards, badges, and refusal rendering', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders relationship_record with Association (as stated by source) and no PubMed link', () => {
    render(
      <EvidenceCard
        isHighlighted={false}
        item={{
          source_id: 'REL-12345',
          source_type: 'relationship_record',
          title: 'Association: CYP2C19 - clopidogrel',
          date: 'unspecified',
          chunk_text: "Relationship record REL-12345: CYP2C19 (Gene) has association 'associated' with clopidogrel (Chemical).",
          entities: ['pg:gene:1559', 'pg:chem:449053'],
          matched_entities: ['pg:gene:1559', 'pg:chem:449053'],
          retrieval_paths: ['graph_lookup'],
          score: 0.05,
          provenance: { association: 'associated' },
        }}
      />
    );
    expect(screen.getByText(/Association \(as stated by source\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Record ID: REL-12345/i)).toBeInTheDocument();
    expect(screen.getByText('Date: No date in data')).toBeInTheDocument();
    expect(screen.getByText('pg:gene:1559')).toBeInTheDocument();
    expect(screen.queryByRole('link')).toBeNull();
  });

  it('does NOT link numeric annotation IDs to PubMed and displays Annotation ID', () => {
    render(
      <EvidenceCard
        isHighlighted={false}
        item={{
          source_id: '1183681642',
          source_type: 'annotation',
          title: 'Variant Annotation 1183681642',
          date: 'unknown',
          chunk_text: 'Patients carrying *2/*3 had reduced platelet inhibition.',
          entities: ['pg:gene:1559'],
          matched_entities: ['pg:gene:1559'],
          retrieval_paths: ['bm25'],
          score: 0.02,
        }}
      />
    );
    expect(screen.getByText(/Annotation ID:/i)).toBeInTheDocument();
    expect(screen.getByText('Variant Annotation 1183681642')).toBeInTheDocument();
    expect(screen.getByText(/\*2\/\*3/)).toBeInTheDocument();
    expect(screen.getByText('Date: No date in data')).toBeInTheDocument();
    expect(screen.queryByRole('link')).toBeNull();
  });

  it('links numeric PubMed PMIDs to PubMed and keeps long excerpts collapsible', () => {
    const longText = 'A'.repeat(260);
    render(
      <EvidenceCard
        isHighlighted={false}
        item={{
          source_id: '19955249',
          source_type: 'pubmed',
          title: 'Clopidogrel pharmacogenomics',
          date: '2009-12',
          chunk_text: longText,
          entities: [],
          matched_entities: [],
          retrieval_paths: ['bm25'],
          score: 0.03,
        }}
      />
    );
    const link = screen.getByRole('link', { name: /PMID: 19955249/i });
    expect(link).toHaveAttribute('href', 'https://pubmed.ncbi.nlm.nih.gov/19955249/');

    const toggleBtn = screen.getByRole('button', { name: /Show full excerpt/i });
    expect(screen.queryByText(longText)).toBeNull();
    fireEvent.click(toggleBtn);
    expect(screen.getByText(longText)).toBeInTheDocument();
    expect(
      screen.queryByText(/Paper cited by a ClinPGx relationship record for this pair/i)
    ).toBeNull();
  });

  it('displays relationship PMID provenance label only on linked PubMed cards', () => {
    render(
      <EvidenceCard
        isHighlighted={false}
        item={{
          source_id: '20801977',
          source_type: 'pubmed',
          title: 'CYP2C19 polymorphism and clopidogrel response',
          date: '2010-09-02',
          chunk_text: 'Abstract content.',
          entities: [],
          matched_entities: ['pg:gene:124', 'pg:chem:449053'],
          retrieval_paths: ['graph', 'linked_via_relationship_pmid'],
          score: 0.032,
          provenance: {
            linked_via_relationship_pmid: true,
            relationship_id: 'rel:c13d31a1998926cc484b972337da816e',
          },
        }}
      />
    );
    expect(
      screen.getByText('Paper cited by a ClinPGx relationship record for this pair')
    ).toBeInTheDocument();
  });

  it('splits semicolon-joined numeric PMIDs into clickable PubMed links with toggle', () => {
    render(
      <EvidenceCard
        isHighlighted={false}
        item={{
          source_id: '12345678;16772608;17697139;17900275;18004210',
          source_type: 'publication',
          title: 'Supporting Publication PMID 12345678;16772608;17697139;17900275;18004210'.padEnd(95, ' '),
          date: 'unspecified',
          chunk_text: 'Supporting PubMed references.',
          entities: [],
          matched_entities: [],
          retrieval_paths: ['graph_pmid_lookup'],
          score: 0.01,
        }}
      />
    );
    expect(screen.getByRole('link', { name: /PMID: 12345678/i })).toHaveAttribute(
      'href',
      'https://pubmed.ncbi.nlm.nih.gov/12345678/'
    );
    expect(screen.getByRole('button', { name: /\+1 more/i })).toBeInTheDocument();
  });

  it('displays conflict, insufficient evidence, and old evidence badges', () => {
    render(
      <EvidencePanel
        highlightedSourceId={null}
        bundle={{
          query: 'test',
          total_items: 1,
          has_sufficient_evidence: false,
          conflicts_detected: true,
          items: [
            {
              source_id: '123456',
              source_type: 'pubmed',
              title: 'Older study',
              date: '2008-05',
              chunk_text: 'Historical data.',
              entities: [],
              matched_entities: [],
              retrieval_paths: ['bm25'],
              score: 0.01,
            },
          ],
        }}
      />
    );
    expect(screen.getByText('Conflicts Detected')).toBeInTheDocument();
    expect(screen.getByText('Insufficient Evidence Threshold')).toBeInTheDocument();
    expect(screen.getByText(/Contains Historical Evidence/i)).toBeInTheDocument();
    // Ungrounded card content must NOT be shown when insufficient_evidence is set
    expect(screen.queryByText('Older study')).toBeNull();
    expect(screen.queryByText('Historical data.')).toBeNull();
    expect(screen.getByText(/ungrounded hits are omitted/i)).toBeInTheDocument();
  });

  it('renders landing page meaning coverage stats per source_type', () => {
    render(
      <App
        initialStats={{
          is_partial: true,
          covered_source_types: ['drug_label', 'guideline'],
          complete_source_types: ['drug_label', 'guideline'],
          per_source_type: {
            annotation: { indexed: 0, expected: 13030, complete: false },
            drug_label: { indexed: 1435, expected: 1435, complete: true },
            guideline: { indexed: 219, expected: 219, complete: true },
            pubmed: { indexed: 0, expected: 7819, complete: false },
          },
        }}
      />
    );
    expect(screen.getByText('Meaning Search Coverage by Source Type')).toBeInTheDocument();
    expect(screen.getByText('Partial Index')).toBeInTheDocument();
    expect(screen.getByText('drug_label')).toBeInTheDocument();
    expect(screen.getByText(/1,435 \/ 1,435/)).toBeInTheDocument();
    expect(screen.getByText('guideline')).toBeInTheDocument();
    expect(screen.getByText(/219 \/ 219/)).toBeInTheDocument();
  });

  it('renders emergency care alert prominently in RefusalPanel and hides evidence area in App', async () => {
    const emergencyMsg =
      'Cannot provide personal dosing advice. If this is happening now, contact local emergency services or seek urgent medical care.';
    render(<RefusalPanel answer={emergencyMsg} flags={['refused', 'refusal_medical_advice']} />);
    expect(screen.getByText(/URGENT MEDICAL NOTICE:/i)).toBeInTheDocument();

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          question: 'chest pain dose?',
          answer: emergencyMsg,
          claims: [],
          evidence_bundle: {
            query: 'chest pain dose?',
            items: [],
            total_items: 0,
            has_sufficient_evidence: false,
            conflicts_detected: false,
          },
          resolved_entities: [],
          flags: ['refused', 'refusal_medical_advice'],
          removed_claims_count: 0,
          disclaimer_text: 'Research prototype, not medical advice',
          answer_mode: 'extractive',
          llm_calls: 0,
          network_calls: 0,
          builder_calls: 0,
        }),
      })
    );

    render(<App />);
    expect(screen.getByText('Research prototype, not medical advice')).toBeInTheDocument();

    const input = screen.getByLabelText(/Enter Gene-Drug Pharmacogenomic Question/i);
    fireEvent.change(input, { target: { value: 'chest pain dose?' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit Question/i }));

    await waitFor(() => {
      expect(screen.getByText('Query Refused by Safety Guard')).toBeInTheDocument();
    });
    expect(screen.queryByText('Retrieved Evidence Bundle')).toBeNull();
  });
});

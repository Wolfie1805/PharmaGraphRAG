import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { HomeStateCards } from '../components/app/HomeStateCards';
import { ResultsHeader } from '../components/app/ResultsHeader';
import { OverviewTable } from '../components/app/OverviewTable';
import { DetailSectionsView } from '../components/app/DetailSectionsView';
import {
  AmbiguityPickerCard,
  BackendOfflineCard,
  HowToReadThisCard,
  InsufficientEvidenceCard,
  RefusalCard,
  UnrecognizedEntityCard,
} from '../components/app/EdgeStates';
import {
  DetailSections,
  OverviewData,
  ResolvedEntity,
  SuggestedNextItem,
} from '../types';

describe('Dashboard Redesign - Stage 3 Component Suite', () => {
  describe('HomeStateCards', () => {
    it('renders 4 supported shape cards and 1 quieter unsupported card', () => {
      const onSelect = vi.fn();
      render(<HomeStateCards onSelectExample={onSelect} />);

      expect(screen.getByText('What can I ask?')).toBeInTheDocument();
      expect(screen.getByText('A medicine')).toBeInTheDocument();
      expect(screen.getByText('A gene')).toBeInTheDocument();
      expect(screen.getByText('A gene and a medicine')).toBeInTheDocument();
      expect(screen.getByText('A variant and a medicine')).toBeInTheDocument();
      expect(screen.getByText('Not supported yet')).toBeInTheDocument();
      expect(screen.getByText('Out of scope')).toBeInTheDocument();
    });

    it('clicking example button triggers onSelectExample callback', () => {
      const onSelect = vi.fn();
      render(<HomeStateCards onSelectExample={onSelect} />);

      const clopidogrelBtn = screen.getByRole('button', { name: 'Try clopidogrel' });
      fireEvent.click(clopidogrelBtn);
      expect(onSelect).toHaveBeenCalledWith('clopidogrel');

      const cypBtn = screen.getByRole('button', { name: 'Try CYP2C19' });
      fireEvent.click(cypBtn);
      expect(onSelect).toHaveBeenCalledWith('CYP2C19');
    });
  });

  describe('ResultsHeader', () => {
    const mockEntities = [
      {
        name: 'CYP2C19',
        canonical_id: 'pg:gene:124',
        type: 'gene',
        status: 'resolved',
        resolved_via: 'text',
      },
      {
        name: 'clopidogrel',
        canonical_id: 'pg:chem:449053',
        type: 'chemical',
        status: 'resolved',
        resolved_via: 'hint',
      },
    ] as unknown as ResolvedEntity[];

    const mockSuggestions: SuggestedNextItem[] = [
      {
        label: 'CYP2C19 ticagrelor',
        entity_ids: ['pg:gene:124', 'pg:chem:999'],
      },
    ];

    it('renders user question, resolved entity chips with via-tag, mode label, and suggestion pills', () => {
      const onSelectSuggestion = vi.fn();
      render(
        <ResultsHeader
          question="CYP2C19 clopidogrel"
          queryMode="pair_detail"
          resolvedEntities={mockEntities}
          suggestedNext={mockSuggestions}
          onSelectSuggestion={onSelectSuggestion}
        />
      );

      expect(screen.getByText('You asked:')).toBeInTheDocument();
      expect(screen.getByText(/"CYP2C19 clopidogrel"/)).toBeInTheDocument();
      expect(screen.getByText('We understood:')).toBeInTheDocument();

      // Entity chips
      expect(screen.getByText('CYP2C19')).toBeInTheDocument();
      expect(screen.getByText('via text')).toBeInTheDocument();
      expect(screen.getByText('clopidogrel')).toBeInTheDocument();
      expect(screen.getByText('via selection')).toBeInTheDocument();

      // Mode label
      expect(screen.getByText('Pair detail')).toBeInTheDocument();

      // Suggestions
      const suggBtn = screen.getByRole('button', { name: /CYP2C19 ticagrelor/i });
      expect(suggBtn).toBeInTheDocument();
      fireEvent.click(suggBtn);
      expect(onSelectSuggestion).toHaveBeenCalledWith('CYP2C19 ticagrelor', ['pg:gene:124', 'pg:chem:999']);
    });
  });

  describe('OverviewTable', () => {
    const mockOverview: OverviewData = {
      total_count: 25,
      offset: 0,
      limit: 20,
      rows: [
        {
          target_id: 'pg:chem:449053',
          target_name: 'clopidogrel',
          target_type: 'chemical',
          other_id: 'pg:gene:124',
          other_name: 'CYP2C19',
          other_type: 'gene',
          chemical_id: 'pg:chem:449053',
          chemical_name: 'clopidogrel',
          gene_id: 'pg:gene:124',
          gene_name: 'CYP2C19',
          association: 'associated',
          curated_count: 55,
          guideline_count: 2,
          drug_label_count: 4,
          annotation_count: 49,
          linked_papers_count: 12,
        },
        {
          target_id: 'pg:chem:449053',
          target_name: 'clopidogrel',
          target_type: 'chemical',
          other_id: 'pg:gene:125',
          other_name: 'CYP2C9',
          other_type: 'gene',
          chemical_id: 'pg:chem:449053',
          chemical_name: 'clopidogrel',
          gene_id: 'pg:gene:125',
          gene_name: 'CYP2C9',
          association: 'associated',
          curated_count: 10,
          guideline_count: 0,
          drug_label_count: 1,
          annotation_count: 9,
          linked_papers_count: 2,
        },
      ],
    };

    it('renders table rows, counts, and handles Open button with entity hints', () => {
      const onOpenPair = vi.fn();
      const onLoadMore = vi.fn();

      render(
        <OverviewTable
          overview={mockOverview}
          queryMode="medicine_overview"
          onOpenPair={onOpenPair}
          onLoadMore={onLoadMore}
        />
      );

      expect(screen.getByText('CYP2C19')).toBeInTheDocument();
      expect(screen.getByText('CYP2C9')).toBeInTheDocument();
      expect(screen.getByText('49')).toBeInTheDocument();
      expect(screen.getByText('12')).toBeInTheDocument();

      // Click Open on first row
      const openButtons = screen.getAllByRole('button', { name: /Open detailed findings/i });
      expect(openButtons.length).toBe(2);
      fireEvent.click(openButtons[0]);

      expect(onOpenPair).toHaveBeenCalledWith('CYP2C19 clopidogrel', ['pg:gene:124', 'pg:chem:449053']);

      // Show more button
      const showMoreBtn = screen.getByRole('button', { name: /Show more/i });
      expect(showMoreBtn).toBeInTheDocument();
      fireEvent.click(showMoreBtn);
      expect(onLoadMore).toHaveBeenCalled();
    });
  });

  describe('DetailSectionsView', () => {
    const mockSections = {
      guidelines: [
        {
          source_id: 'CPIC_GUIDELINE_1',
          source_type: 'guideline',
          title: 'CPIC Guideline for Clopidogrel and CYP2C19',
          chunk_text: 'Intermediate and poor metabolizers have reduced active metabolite levels.',
          source: 'CPIC',
          url: 'https://cpicpgx.org',
        },
      ],
      drug_labels: [
        {
          source_id: 'FDA_LABEL_1',
          source_type: 'drug_label',
          title: 'Plavix Prescribing Information',
          chunk_text: 'Boxed warning on diminished antiplatelet effect in CYP2C19 poor metabolizers.',
          source: 'FDA',
          testing_level: 'Actionable PGx',
          biomarker_flag: 'On FDA Biomarker List',
        },
      ],
      variant_findings: [
        {
          variant_tag: 'CYP2C19*2',
          display_name: 'CYP2C19*2 (Loss of function)',
          canonical_id: 'pg:var:166154053',
          findings: [
            {
              source_id: 'ANN_1',
              title: 'CYP2C19*2 is associated with clopidogrel resistance',
              sentence: 'Patients carrying the *2 allele exhibit significantly reduced platelet inhibition.',
              significance: 'yes',
              phenotype_category: 'Metabolism/PK',
              direction_of_effect: 'decreased',
              population_types: 'in people with coronary artery disease',
              source_columns: {
                significance: 'var_drug_ann.Significance',
                direction_of_effect: 'var_drug_ann.Direction of effect',
              },
            },
          ],
        },
      ],
      linked_papers: [
        {
          source_id: 'pmid:18946070',
          source_type: 'paper',
          title: 'Cytochrome P450 2C19 and cardiovascular outcomes',
          chunk_text: 'Mega JL et al., NEJM 2009. Association between CYP2C19 genotype and clinical efficacy.',
          source: 'PubMed',
        },
      ],
      recorded_relationships: [
        {
          source_id: 'REL_1',
          source_type: 'relationship',
          title: 'CYP2C19 - clopidogrel association',
          chunk_text: 'Curated association in ClinPGx.',
          source: 'ClinPGx',
        },
      ],
    } as unknown as DetailSections;

    it('renders all 5 detail sections in strict required order and displays structured column badges', () => {
      const onCitationClick = vi.fn();
      const { container } = render(
        <DetailSectionsView
          sections={mockSections}
          claims={[
            {
              text: 'CYP2C19 poor metabolizers exhibit decreased platelet response.',
              source_ids: ['CPIC_GUIDELINE_1'],
            },
          ]}
          answer="Extractive summary answer text."
          onCitationClick={onCitationClick}
        />
      );

      // Section 1: Clinical Guidelines
      expect(screen.getByRole('heading', { level: 3, name: /1\. Clinical Guidelines/i })).toBeInTheDocument();
      expect(screen.getByText('CPIC Guideline for Clopidogrel and CYP2C19')).toBeInTheDocument();

      // Section 2: Regulatory Drug Labels
      expect(screen.getByRole('heading', { level: 3, name: /2\. Drug Label Annotations/i })).toBeInTheDocument();
      expect(screen.getByText('Plavix Prescribing Information')).toBeInTheDocument();
      expect(screen.getByText('Drug Label')).toBeInTheDocument();

      // Section 3: Variant-Level Findings
      expect(screen.getByRole('heading', { level: 3, name: /3\. Variant-Level Clinical Findings/i })).toBeInTheDocument();
      expect(screen.getByText('CYP2C19*2')).toBeInTheDocument();

      // Structured field badges
      expect(screen.getByText('decreased')).toBeInTheDocument();
      expect(screen.getByText('Metabolism/PK')).toBeInTheDocument();
      expect(screen.getByText('in people with coronary artery disease')).toBeInTheDocument();

      // Section 4: Cited Literature
      expect(screen.getByRole('heading', { level: 3, name: /4\. Papers Cited/i })).toBeInTheDocument();
      expect(screen.getByText(/Cytochrome P450 2C19 and cardiovascular outcomes/i)).toBeInTheDocument();
      expect(screen.getByText('PMID: 18946070')).toBeInTheDocument();

      // Section 5: Recorded Relationships
      expect(screen.getByRole('heading', { level: 3, name: /5\. Recorded Relationships/i })).toBeInTheDocument();
      expect(screen.getByText(/CYP2C19 - clopidogrel association/i)).toBeInTheDocument();

      // Verify DOM ordering of section headers
      const headings = container.querySelectorAll('h3.section-title');
      expect(headings.length).toBe(5);
      expect(headings[0].textContent).toContain('1. Clinical Guidelines');
      expect(headings[1].textContent).toContain('2. Drug Label Annotations');
      expect(headings[2].textContent).toContain('3. Variant-Level Clinical Findings');
      expect(headings[3].textContent).toContain('4. Papers Cited');
      expect(headings[4].textContent).toContain('5. Recorded Relationships');
    });

    it('applies font-mono class to star alleles and rsIDs', () => {
      render(
        <DetailSectionsView
          sections={mockSections}
          claims={[]}
          answer="Test answer"
        />
      );

      const monoElements = document.querySelectorAll('.font-mono');
      expect(monoElements.length).toBeGreaterThan(0);
      const textContents = Array.from(monoElements).map((el) => el.textContent);
      expect(textContents.some((t) => t?.includes('CYP2C19*2'))).toBe(true);
    });
  });

  describe('Edge States', () => {
    it('renders AmbiguityPickerCard with candidates and handles selection', () => {
      const onSelect = vi.fn();
      const mockAmbEntity = {
        name: 'CYP2C19*2',
        canonical_id: '',
        type: 'variant',
        status: 'ambiguous',
        candidates: [
          {
            canonical_id: 'pg:var:166154053',
            display_name: 'CYP2C19*2 (Single Nucleotide Variant)',
            entity_type: 'variant',
          },
          {
            canonical_id: 'pg:haplo:165980635',
            display_name: 'CYP2C19*2 (Haplotype / Star Allele)',
            entity_type: 'haplotype',
          },
        ],
      } as unknown as ResolvedEntity;

      render(
        <AmbiguityPickerCard
          ambiguousEntity={mockAmbEntity}
          onSelectCandidate={onSelect}
        />
      );

      expect(screen.getByText(/Ambiguity Detected/i)).toBeInTheDocument();
      expect(screen.getByText(/CYP2C19\*2 \(Single Nucleotide Variant\)/i)).toBeInTheDocument();
      expect(screen.getByText(/CYP2C19\*2 \(Haplotype \/ Star Allele\)/i)).toBeInTheDocument();

      const candidateButtons = screen.getAllByRole('button', { name: 'Select' });
      expect(candidateButtons.length).toBe(2);
      fireEvent.click(candidateButtons[0]);
      expect(onSelect).toHaveBeenCalledWith(
        'pg:var:166154053',
        'CYP2C19*2 (Single Nucleotide Variant)',
        'CYP2C19*2'
      );
    });

    it('renders RefusalCard with safety policy and prompt templates', () => {
      const onSelect = vi.fn();
      render(
        <RefusalCard
          answer="Personal medical advice refused."
          flags={['clinical_dosing_refused']}
          onSelectTemplate={onSelect}
        />
      );

      expect(screen.getByText(/Research Prototype Safety Boundary/i)).toBeInTheDocument();
      expect(screen.getByText(/Safety Policy:/i)).toBeInTheDocument();
      expect(screen.getByText('clinical_dosing_refused')).toBeInTheDocument();

      // Check prompt templates
      expect(screen.getByText('A gene and a medicine')).toBeInTheDocument();
    });

    it('renders UnrecognizedEntityCard with guidance and prompt templates', () => {
      const onSelect = vi.fn();
      render(
        <UnrecognizedEntityCard
          term="dolo 650"
          onSelectTemplate={onSelect}
        />
      );

      expect(screen.getByText(/Entity Not Found in Pharmacogenomics Data/i)).toBeInTheDocument();
      expect(screen.getByText(/We could not match "dolo 650"/i)).toBeInTheDocument();
    });

    it('renders InsufficientEvidenceCard with counts', () => {
      render(<InsufficientEvidenceCard totalItems={1} minRequired={3} />);
      expect(screen.getByText('Insufficient Curated Evidence')).toBeInTheDocument();
      expect(screen.getByText(/Retrieved 1 grounded items \(minimum required: 3\)/i)).toBeInTheDocument();
    });

    it('renders BackendOfflineCard with retry button', () => {
      const onRetry = vi.fn();
      render(<BackendOfflineCard onRetry={onRetry} />);
      expect(screen.getByText('Backend Service Offline')).toBeInTheDocument();

      const retryBtn = screen.getByRole('button', { name: /Retry Connection/i });
      fireEvent.click(retryBtn);
      expect(onRetry).toHaveBeenCalled();
    });

    it('toggles HowToReadThisCard open and closed', () => {
      render(<HowToReadThisCard />);
      const toggleBtn = screen.getByRole('button', { name: /How to read this/i });
      expect(screen.queryByText(/Overview vs\. Detail View/i)).not.toBeInTheDocument();

      // Click to expand
      fireEvent.click(toggleBtn);
      expect(screen.getByText(/Overview vs\. Detail View/i)).toBeInTheDocument();
      expect(screen.getByText(/What is a Star Allele \(\*\)\?/i)).toBeInTheDocument();
      expect(screen.getByText(/Citation Verification/i)).toBeInTheDocument();

      // Click to collapse
      fireEvent.click(toggleBtn);
      expect(screen.queryByText(/Overview vs\. Detail View/i)).not.toBeInTheDocument();
    });
  });

  describe('XSS and Plain Text Safety', () => {
    it('renders planted script and HTML strings strictly as plain text', () => {
      const xssScript = '<script>alert("xss")</script>';
      const xssImg = '<img src=x onerror=alert(1) />';

      render(
        <DetailSectionsView
          sections={{
            guidelines: [
              {
                source_id: 'XSS_1',
                source_type: 'guideline',
                title: xssScript,
                chunk_text: xssImg,
              },
            ],
            drug_labels: [],
            variant_findings: [],
            linked_papers: [],
            recorded_relationships: [],
          } as unknown as DetailSections}
          claims={[
            {
              text: xssScript,
              source_ids: ['XSS_1'],
            },
          ]}
          answer={xssImg}
        />
      );

      // Verify no script or img elements were inserted into DOM
      expect(document.querySelector('script')).toBeNull();
      expect(document.querySelector('img[src="x"]')).toBeNull();

      // Verify text rendered literally as text
      expect(screen.getAllByText(xssScript).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(xssImg).length).toBeGreaterThanOrEqual(1);
    });
  });
});

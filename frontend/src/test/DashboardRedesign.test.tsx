import { render, screen, fireEvent, within } from '@testing-library/react';
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
      expect(screen.getAllByText(/ClinPGx relationship record states: associated/i).length).toBe(2);
      expect(
        screen.getByText(
          /This is the value stored in the source record\. It is not a judgement by this tool and is unrelated to name ambiguity\./i
        )
      ).toBeInTheDocument();
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
          provenance: { 'guideline.source': 'CPIC' },
        },
        {
          source_id: 'NO_SRC_GUIDELINE_2',
          source_type: 'guideline',
          title: 'Guideline Without Source Field',
          chunk_text: 'Body text without issuing body field.',
          provenance: {},
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
        {
          variant_tag: 'CYP2C19*3',
          display_name: 'CYP2C19*3',
          findings: [{ source_id: 'ANN_2', title: 'T2', sentence: 'Finding 2 sentence.', source_columns: {} }],
        },
        {
          variant_tag: 'CYP2C19*17',
          display_name: 'CYP2C19*17',
          findings: [{ source_id: 'ANN_3', title: 'T3', sentence: 'Finding 3 sentence.', source_columns: {} }],
        },
        {
          variant_tag: 'CYP2C19*4',
          display_name: 'CYP2C19*4',
          findings: [{ source_id: 'ANN_4', title: 'T4', sentence: 'Fourth group hidden initially.', source_columns: {} }],
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
          source_type: 'relationship_record',
          title: 'CYP2C19 - clopidogrel association',
          chunk_text: 'Curated association in ClinPGx.',
          provenance: { association: 'ambiguous' },
        },
      ],
    } as unknown as DetailSections;

    it('renders guidelines open by default, collapses other sections and variant groups beyond 3, and displays jump links', () => {
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

      // Jump links present with counts
      const jumpNav = screen.getByRole('navigation', { name: /Evidence section jump links/i });
      expect(within(jumpNav).getByRole('button', { name: /Guideline annotations \(2\)/i })).toBeInTheDocument();
      expect(within(jumpNav).getByRole('button', { name: /Drug labels \(1\)/i })).toBeInTheDocument();
      expect(within(jumpNav).getByRole('button', { name: /Variant findings \(4\)/i })).toBeInTheDocument();
      expect(within(jumpNav).getByRole('button', { name: /Papers cited \(1\)/i })).toBeInTheDocument();
      expect(within(jumpNav).getByRole('button', { name: /Recorded relationships \(1\)/i })).toBeInTheDocument();

      // Section 1: Guideline annotations (ClinPGx) is OPEN by default
      expect(screen.getByRole('heading', { level: 3, name: /1\. Guideline annotations \(ClinPGx\) \(2\)/i })).toBeInTheDocument();
      expect(screen.getByText('CPIC Guideline for Clopidogrel and CYP2C19')).toBeInTheDocument();
      expect(screen.getByText('guideline.source: CPIC')).toBeInTheDocument();
      // Second guideline has no guideline.source -> only 1 badge rendered
      expect(screen.getAllByText(/guideline\.source:/i).length).toBe(1);

      // Sections 2, 3, 4, 5 are COLLAPSED by default
      expect(screen.queryByText('Plavix Prescribing Information')).not.toBeInTheDocument();
      expect(screen.queryByText('CYP2C19*2')).not.toBeInTheDocument();
      expect(screen.queryByText('PMID: 18946070')).not.toBeInTheDocument();
      expect(screen.queryByText(/CYP2C19 - clopidogrel association/i)).not.toBeInTheDocument();

      // Expand Section 2: Drug labels
      fireEvent.click(screen.getByRole('button', { name: /2\. Drug Label Annotations/i }));
      expect(screen.getByText('Plavix Prescribing Information')).toBeInTheDocument();

      // Expand Section 3: Variant findings (first 3 groups open, 4th collapsed)
      fireEvent.click(screen.getByRole('button', { name: /3\. Variant-Level Clinical Findings/i }));
      expect(screen.getByText('CYP2C19*2')).toBeInTheDocument();
      expect(screen.getByText('decreased')).toBeInTheDocument();
      expect(screen.getByText('Finding 2 sentence.')).toBeInTheDocument();
      expect(screen.getByText('Finding 3 sentence.')).toBeInTheDocument();
      expect(screen.queryByText('Fourth group hidden initially.')).not.toBeInTheDocument();

      // Expand Section 4: Papers cited
      fireEvent.click(screen.getByRole('button', { name: /4\. Papers Cited/i }));
      expect(screen.getByText('PMID: 18946070')).toBeInTheDocument();

      // Expand Section 5: Recorded relationships
      fireEvent.click(screen.getByRole('button', { name: /5\. Recorded Relationships/i }));
      expect(screen.getByText(/ClinPGx relationship record states: ambiguous/i)).toBeInTheDocument();
      expect(
        screen.getByText(
          /This is the value stored in the source record\. It is not a judgement by this tool and is unrelated to name ambiguity\./i
        )
      ).toBeInTheDocument();

      // Verify DOM ordering of section headers
      const headings = container.querySelectorAll('h3.section-title');
      expect(headings.length).toBe(5);
      expect(headings[0].textContent).toContain('1. Guideline annotations (ClinPGx)');
      expect(headings[1].textContent).toContain('2. Drug Label Annotations');
      expect(headings[2].textContent).toContain('3. Variant-Level Clinical Findings');
      expect(headings[3].textContent).toContain('4. Papers Cited');
      expect(headings[4].textContent).toContain('5. Recorded Relationships');
    });

    it('renders gene-medicine pair labels and paged all linked papers list', () => {
      const extendedSections = {
        ...mockSections,
        guidelines_label: 'Records for this gene-medicine pair (not variant-specific)',
        drug_labels_label: 'Records for this gene-medicine pair (not variant-specific)',
        all_linked_papers: [
          { source_id: '1000001', source_type: 'pubmed', title: 'Paper One', chunk_text: 'Text 1' },
          { source_id: '1000002', source_type: 'pubmed', title: 'Paper Two', chunk_text: 'Text 2' },
          { source_id: '1000003', source_type: 'pubmed', title: 'Paper Three', chunk_text: 'Text 3' },
          { source_id: '1000004', source_type: 'pubmed', title: 'Paper Four', chunk_text: 'Text 4' },
          { source_id: '1000005', source_type: 'pubmed', title: 'Paper Five', chunk_text: 'Text 5' },
          { source_id: '1000006', source_type: 'pubmed', title: 'Paper Six', chunk_text: 'Text 6' },
        ],
      } as unknown as DetailSections;

      render(
        <DetailSectionsView
          sections={extendedSections}
          claims={[]}
          answer="Test answer"
        />
      );

      const pairLabels = screen.getAllByText('Records for this gene-medicine pair (not variant-specific)');
      expect(pairLabels.length).toBe(2);

      // Open Section 4 first (collapsed by default)
      fireEvent.click(screen.getByRole('button', { name: /4\. Papers Cited/i }));

      const toggleBtn = screen.getByRole('button', { name: /Show all linked papers \(6 in corpus\)/i });
      expect(toggleBtn).toBeInTheDocument();
      fireEvent.click(toggleBtn);

      expect(screen.getByText('Paper One')).toBeInTheDocument();
      expect(screen.getByText('Paper Five')).toBeInTheDocument();
      expect(screen.queryByText('Paper Six')).not.toBeInTheDocument();

      const showMoreBtn = screen.getByRole('button', { name: /Show more linked papers \(5 of 6\)/i });
      fireEvent.click(showMoreBtn);
      expect(screen.getByText('Paper Six')).toBeInTheDocument();
    });

    it('applies font-mono class to star alleles and rsIDs', () => {
      render(
        <DetailSectionsView
          sections={mockSections}
          claims={[]}
          answer="Test answer"
        />
      );

      // Open Variant Findings section first
      fireEvent.click(screen.getByRole('button', { name: /3\. Variant-Level Clinical Findings/i }));

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

      expect(screen.getByText(/Name matches several items/i)).toBeInTheDocument();
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

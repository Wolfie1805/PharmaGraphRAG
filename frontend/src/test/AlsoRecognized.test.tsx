import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ResultsHeader } from '../components/app/ResultsHeader';
import { AlsoRecognizedItem, ResolvedEntity } from '../types';

describe('ResultsHeader - Also Recognized Section', () => {
  const dummyResolvedEntities: ResolvedEntity[] = [
    {
      name: 'CYP2D6',
      query: 'CYP2D6',
      status: 'resolved',
      canonical_id: 'pg:gene:128',
      entity_type: 'gene',
      candidates: [
        {
          canonical_id: 'pg:gene:128',
          display_name: 'CYP2D6',
          entity_type: 'gene',
          primary_source_id: '128',
          normalized_name: 'cyp2d6',
          is_drug: false,
          defined_by: 'ClinPGx',
          is_ambiguous: false,
        },
      ],
    },
    {
      name: 'codeine',
      query: 'codeine',
      status: 'resolved',
      canonical_id: 'pg:chem:449088',
      entity_type: 'chemical',
      candidates: [
        {
          canonical_id: 'pg:chem:449088',
          display_name: 'codeine',
          entity_type: 'chemical',
          primary_source_id: '449088',
          normalized_name: 'codeine',
          is_drug: true,
          defined_by: 'ClinPGx',
          is_ambiguous: false,
        },
      ],
    },
  ];

  const dummyAlsoRecognized: AlsoRecognizedItem[] = [
    {
      name: 'Pain',
      type: 'phenotype',
      canonical_id: 'pg:phenotype:445208',
    },
  ];

  it('renders "Also recognized (not used to narrow results): <name> (<type>)" with chips and help text', () => {
    const handleSelect = vi.fn();
    render(
      <ResultsHeader
        question="CYP2D6 codeine pain"
        queryMode="pair_detail"
        resolvedEntities={dummyResolvedEntities}
        alsoRecognized={dummyAlsoRecognized}
        onSelectSuggestion={handleSelect}
      />
    );

    // Primary entities in "We understood"
    expect(screen.getByText(/We understood:/i)).toBeInTheDocument();
    expect(screen.getByText('CYP2D6')).toBeInTheDocument();
    expect(screen.getByText('codeine')).toBeInTheDocument();

    // Also recognized row header
    expect(
      screen.getByText(/Also recognized \(not used to narrow results\):/i)
    ).toBeInTheDocument();

    // Chip with <name> (<type>)
    expect(screen.getByText('Pain')).toBeInTheDocument();
    expect(screen.getByText('(phenotype)')).toBeInTheDocument();

    // Help text
    expect(
      screen.getByText(
        /These terms were recognized as clinical entities but are not used to filter, rank, or exclude evidence\./i
      )
    ).toBeInTheDocument();
  });

  it('does not render also recognized row when alsoRecognized is empty', () => {
    const handleSelect = vi.fn();
    render(
      <ResultsHeader
        question="CYP2D6 codeine"
        queryMode="pair_detail"
        resolvedEntities={dummyResolvedEntities}
        alsoRecognized={[]}
        onSelectSuggestion={handleSelect}
      />
    );

    expect(screen.getByText(/We understood:/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/Also recognized \(not used to narrow results\):/i)
    ).not.toBeInTheDocument();
  });

  it('excludes also-recognized entities from "We understood" to avoid duplication', () => {
    const handleSelect = vi.fn();
    // Suppose resolvedEntities contains both CYP2D6 and Pain
    const entitiesWithPhenotype: ResolvedEntity[] = [
      ...dummyResolvedEntities,
      {
        name: 'Pain',
        query: 'pain',
        status: 'resolved',
        canonical_id: 'pg:phenotype:445208',
        entity_type: 'phenotype',
        candidates: [
          {
            canonical_id: 'pg:phenotype:445208',
            display_name: 'Pain',
            entity_type: 'phenotype',
            primary_source_id: '445208',
            normalized_name: 'pain',
            is_drug: false,
            defined_by: 'ClinPGx',
            is_ambiguous: false,
          },
        ],
      },
    ];

    render(
      <ResultsHeader
        question="CYP2D6 codeine pain"
        queryMode="pair_detail"
        resolvedEntities={entitiesWithPhenotype}
        alsoRecognized={dummyAlsoRecognized}
        onSelectSuggestion={handleSelect}
      />
    );

    // "We understood" should have CYP2D6 and codeine, but not Pain in the understood chips
    const understoodChips = screen.getAllByRole('listitem');
    expect(understoodChips).toHaveLength(3); // 2 in We understood + 1 in Also recognized
    // Only 1 Pain chip exists (in the also-recognized section)
    const painElements = screen.getAllByText('Pain');
    expect(painElements).toHaveLength(1);
  });
});

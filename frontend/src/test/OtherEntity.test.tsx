import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { OtherEntityCard } from '../components/app/EdgeStates';

describe('OtherEntityCard', () => {
  it('renders recognized entity chips, lead text, and template buttons', () => {
    const handleSelect = vi.fn();
    render(
      <OtherEntityCard
        resolvedEntities={[
          {
            name: 'Pain',
            query: 'pain',
            status: 'resolved',
            canonical_id: 'pg:phenotype:445208',
            candidate_types: ['phenotype'],
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
        ]}
        answer="We recognized 'Pain' (phenotype), but this prototype currently only provides curated evidence overviews for genes, medicines, variants, and gene-medicine pairs."
        onSelectTemplate={handleSelect}
      />
    );

    // Title and lead text
    expect(
      screen.getByText(/Entity Recognized \(No Dedicated Evidence Overview\)/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/We recognized 'Pain' \(phenotype\)/i)).toBeInTheDocument();

    // Entity chip
    expect(screen.getByText('Pain')).toBeInTheDocument();
    expect(screen.getByText('(phenotype)')).toBeInTheDocument();

    // Template mini-cards
    const tryBtn = screen.getByRole('button', { name: /Try "CYP2C19 clopidogrel"/i });
    expect(tryBtn).toBeInTheDocument();
    fireEvent.click(tryBtn);
    expect(handleSelect).toHaveBeenCalledWith('CYP2C19 clopidogrel');
  });
});

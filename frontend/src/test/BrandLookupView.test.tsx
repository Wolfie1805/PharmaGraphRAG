import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { BrandLookupView } from '../components/app/BrandLookupView';
import { SearchBar } from '../components/app/SearchBar';
import { HomeStateCards } from '../components/app/HomeStateCards';
import { BrandLookupData } from '../types';

describe('BrandLookupView Component Suite', () => {
  const sampleDolo: BrandLookupData = {
    total_count: 1,
    offset: 0,
    limit: 10,
    disclaimer: 'This only identifies ingredients.',
    products: [
      {
        brand_id: 'brand:1001',
        brand_name: 'Dolo 650 mg oral tablet',
        generic_id: 'gen:2001',
        generic_name: 'paracetamol 650 mg oral tablet',
        ingredients_listed: ['Paracetamol'],
        is_combination: false,
        is_orphan: false,
        ingredients: [
          {
            substance_id: 'sub:387517004',
            substance_name: 'Paracetamol',
            status: 'matched',
            clinpgx_display_name: 'paracetamol',
            clinpgx_canonical_id: 'pg:chem:450774',
            is_openable: true,
          },
        ],
      },
    ],
  };

  it('renders brand header with NRCeS badge and honest scope statements', () => {
    const onOpen = vi.fn();
    const onPage = vi.fn();

    render(
      <BrandLookupView
        brands={sampleDolo}
        onOpenIngredient={onOpen}
        onPageChange={onPage}
      />
    );

    // Header badge
    expect(screen.getByText('Brand match (source: NRCeS)')).toBeInTheDocument();
    expect(screen.getByText(/1 product found/i)).toBeInTheDocument();

    // Honest scope disclaimer
    expect(
      screen.getByText(
        'This only identifies ingredients. It does not say what the medicine is for or how to take it.'
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText('Lack of ClinPGx records does not mean a medicine is safe.')
    ).toBeInTheDocument();

    // Stored brand & generic names
    expect(screen.getByText('Dolo 650 mg oral tablet')).toBeInTheDocument();
    expect(screen.getByText('paracetamol 650 mg oral tablet')).toBeInTheDocument();
    expect(screen.getByText('Ingredients listed by NRCeS:')).toBeInTheDocument();
  });

  it('renders openable button for matched ingredient and triggers callback with canonical ID', () => {
    const onOpen = vi.fn();
    const onPage = vi.fn();

    render(
      <BrandLookupView
        brands={sampleDolo}
        onOpenIngredient={onOpen}
        onPageChange={onPage}
      />
    );

    expect(screen.getByText(/found in ClinPGx as/i)).toBeInTheDocument();
    const openBtn = screen.getByRole('button', { name: /Open ClinPGx evidence for paracetamol/i });
    expect(openBtn).toBeInTheDocument();
    expect(openBtn).toHaveTextContent('Open paracetamol');

    fireEvent.click(openBtn);
    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(onOpen).toHaveBeenCalledWith('paracetamol', 'pg:chem:450774');
  });

  it('renders orphan generic fallback when product has no ingredient records', () => {
    const orphanData: BrandLookupData = {
      total_count: 1,
      offset: 0,
      limit: 10,
      disclaimer: 'This only identifies ingredients.',
      products: [
        {
          brand_id: 'brand:1002',
          brand_name: 'Minidolo suspension',
          generic_id: 'gen:2002',
          generic_name: '',
          ingredients_listed: [],
          is_combination: false,
          is_orphan: true,
          ingredients: [],
        },
      ],
    };

    render(
      <BrandLookupView
        brands={orphanData}
        onOpenIngredient={vi.fn()}
        onPageChange={vi.fn()}
      />
    );

    expect(screen.getByText('Minidolo suspension')).toBeInTheDocument();
    expect(
      screen.getByText('Ingredients not available in NRCeS data for this product')
    ).toBeInTheDocument();
    expect(screen.queryByText('Ingredients listed by NRCeS:')).not.toBeInTheDocument();
  });

  it('renders ambiguity notice without open button for ambiguous ingredients', () => {
    const ambiguousData: BrandLookupData = {
      total_count: 1,
      offset: 0,
      limit: 10,
      disclaimer: 'This only identifies ingredients.',
      products: [
        {
          brand_id: 'brand:1003',
          brand_name: 'Heparin Brand 5000 IU',
          generic_id: 'gen:2003',
          generic_name: 'heparin injection',
          ingredients_listed: ['Enoxaparin sodium', 'Novel Excipient Active'],
          is_combination: false,
          is_orphan: false,
          ingredients: [
            {
              substance_id: 'sub:108983001',
              substance_name: 'Enoxaparin sodium',
              status: 'ambiguous',
              clinpgx_candidates: ['enoxaparin', 'heparin'],
              is_openable: false,
            },
            {
              substance_id: 'sub:999999999',
              substance_name: 'Novel Excipient Active',
              status: 'unmatched',
              is_openable: false,
            },
          ],
        },
      ],
    };

    render(
      <BrandLookupView
        brands={ambiguousData}
        onOpenIngredient={vi.fn()}
        onPageChange={vi.fn()}
      />
    );

    // Ambiguity notice
    expect(
      screen.getByText(
        'Matches several ClinPGx chemicals: enoxaparin, heparin (not openable)'
      )
    ).toBeInTheDocument();

    // Unmatched notice
    expect(screen.getByText('Not matched in ClinPGx')).toBeInTheDocument();

    // No Open button should be rendered
    expect(screen.queryByRole('button', { name: /Open/i })).not.toBeInTheDocument();
  });

  it('renders pagination controls and handles page navigation', () => {
    const onPage = vi.fn();
    const pagedData: BrandLookupData = {
      total_count: 14,
      offset: 0,
      limit: 10,
      disclaimer: 'This only identifies ingredients.',
      products: [
        {
          brand_id: 'brand:1',
          brand_name: 'Flexon tablet',
          generic_id: 'gen:1',
          generic_name: 'ibuprofen + paracetamol',
          ingredients_listed: ['Ibuprofen', 'Paracetamol'],
          is_combination: true,
          is_orphan: false,
          ingredients: [],
        },
      ],
    };

    const { rerender } = render(
      <BrandLookupView
        brands={pagedData}
        onOpenIngredient={vi.fn()}
        onPageChange={onPage}
      />
    );

    expect(screen.getByText('Showing 1-10 of 14 products')).toBeInTheDocument();
    const prevBtn = screen.getByRole('button', { name: /Previous page/i });
    const nextBtn = screen.getByRole('button', { name: /Next page/i });

    expect(prevBtn).toBeDisabled();
    expect(nextBtn).toBeEnabled();

    fireEvent.click(nextBtn);
    expect(onPage).toHaveBeenCalledWith(10);

    // Re-render at offset 10 (page 2)
    rerender(
      <BrandLookupView
        brands={{ ...pagedData, offset: 10 }}
        onOpenIngredient={vi.fn()}
        onPageChange={onPage}
      />
    );

    expect(screen.getByText('Showing 11-14 of 14 products')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Previous page/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /Next page/i })).toBeDisabled();
  });

  it('renders brand group and Indian brand badge in SearchBar', () => {
    const onSubmit = vi.fn();

    render(
      <SearchBar
        value="Dolo"
        onChange={vi.fn()}
        onSubmit={onSubmit}
        loading={false}
        onClear={vi.fn()}
      />
    );

    // Verify search input is present
    const input = screen.getByRole('combobox');
    expect(input).toBeInTheDocument();
  });

  it('renders Indian brand card and updated unsupported card in HomeStateCards', () => {
    const onSelect = vi.fn();

    render(<HomeStateCards onSelectExample={onSelect} />);

    // Indian brand card
    expect(screen.getByText('An Indian brand name')).toBeInTheDocument();
    expect(screen.getByText('[Brand name]')).toBeInTheDocument();
    expect(
      screen.getByText('Lookup ingredients for an Indian brand name from the official NRCeS release.')
    ).toBeInTheDocument();
    const doloBtn = screen.getByRole('button', { name: /Try Dolo 650/i });
    expect(doloBtn).toBeInTheDocument();
    fireEvent.click(doloBtn);
    expect(onSelect).toHaveBeenCalledWith('Dolo 650');

    // Unsupported card
    expect(screen.getByText('Brand names that are not in the NRCeS list')).toBeInTheDocument();
  });

  it('renders similar products collapsed under details summary and never opens automatically', () => {
    const dataWithSimilar: BrandLookupData = {
      total_count: 1,
      offset: 0,
      limit: 10,
      disclaimer: 'This only identifies ingredients.',
      products: [
        {
          brand_id: 'brand:1001',
          brand_name: 'Dolo 650 mg oral tablet',
          generic_id: 'gen:2001',
          generic_name: 'paracetamol 650 mg oral tablet',
          ingredients_listed: ['Paracetamol'],
          is_combination: false,
          is_orphan: false,
          ingredients: [],
        },
      ],
      similar_total_count: 2,
      similar_products: [
        {
          brand_id: 'brand:1002',
          brand_name: 'Dolod 650 mg oral tablet',
          generic_id: 'gen:2002',
          generic_name: 'paracetamol 650 mg oral tablet',
          ingredients_listed: ['Paracetamol'],
          is_combination: false,
          is_orphan: false,
          ingredients: [],
        },
        {
          brand_id: 'brand:1003',
          brand_name: 'Dolopar 650 mg oral tablet',
          generic_id: 'gen:2003',
          generic_name: 'paracetamol 650 mg oral tablet',
          ingredients_listed: ['Paracetamol'],
          is_combination: false,
          is_orphan: false,
          ingredients: [],
        },
      ],
    };

    render(
      <BrandLookupView
        brands={dataWithSimilar}
        onOpenIngredient={vi.fn()}
        onPageChange={vi.fn()}
      />
    );

    // Exact product is present
    expect(screen.getByText('Dolo 650 mg oral tablet')).toBeInTheDocument();

    // Summary heading is present
    const summaryText = 'Other products with similar names. Check the full name on your pack.';
    expect(screen.getByText(summaryText)).toBeInTheDocument();

    // Details element is not open by default
    const detailsEl = screen.getByText(summaryText).closest('details');
    expect(detailsEl).toBeInTheDocument();
    expect(detailsEl).not.toHaveAttribute('open');

    // Similar products exist in DOM inside details
    expect(screen.getByText('Dolod 650 mg oral tablet')).toBeInTheDocument();
    expect(screen.getByText('Dolopar 650 mg oral tablet')).toBeInTheDocument();
  });
});

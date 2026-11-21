import React from 'react';
import { BrandLookupData, BrandProductItem } from '../../types';

interface BrandLookupViewProps {
  brands: BrandLookupData;
  onOpenIngredient: (displayName: string, canonicalId: string) => void;
  onPageChange: (newOffset: number) => void;
}

export const BrandLookupView: React.FC<BrandLookupViewProps> = ({
  brands,
  onOpenIngredient,
  onPageChange,
}) => {
  const { total_count, offset, limit, products, similar_products } = brands;
  const start = total_count > 0 ? offset + 1 : 0;
  const end = Math.min(offset + limit, total_count);

  const renderProductCard = (product: BrandProductItem) => (
    <article key={product.brand_id} className="brand-product-card edge-card" role="listitem">
      <div className="product-header">
        <h4 className="product-brand-name">{product.brand_name}</h4>
        {product.generic_name ? (
          <div className="product-generic-name">
            <span className="generic-label">Generic formulation:</span>{' '}
            <span className="generic-val">{product.generic_name}</span>
          </div>
        ) : null}
      </div>

      {/* Orphan check: "Ingredients not available in NRCeS data for this product" (orphan generic) */}
      {product.is_orphan || product.ingredients.length === 0 ? (
        <div className="product-orphan-fallback" role="note">
          Ingredients not available in NRCeS data for this product
        </div>
      ) : (
        <div className="product-ingredients-section">
          <div className="ingredients-header">Ingredients listed by NRCeS:</div>
          <ul className="ingredients-list">
            {product.ingredients.map((ing) => (
              <li key={ing.substance_id} className="ingredient-item">
                <div className="ingredient-info">
                  <span className="ingredient-substance-name">{ing.substance_name}</span>
                  <span className="ingredient-substance-id font-mono">[{ing.substance_id}]</span>
                </div>

                <div className="ingredient-status-row">
                  {ing.is_openable && ing.clinpgx_display_name && ing.clinpgx_canonical_id ? (
                    <div className="ingredient-matched">
                      <span className="status-label">
                        found in ClinPGx as <strong>{ing.clinpgx_display_name}</strong>
                      </span>
                      <button
                        type="button"
                        className="btn-open-ingredient btn-glow"
                        onClick={() => onOpenIngredient(ing.clinpgx_display_name!, ing.clinpgx_canonical_id!)}
                        aria-label={`Open ClinPGx evidence for ${ing.clinpgx_display_name}`}
                      >
                        Open {ing.clinpgx_display_name}
                      </button>
                    </div>
                  ) : ing.status === 'ambiguous' ? (
                    <div className="ingredient-ambiguous">
                      Matches several ClinPGx chemicals: {ing.clinpgx_candidates && ing.clinpgx_candidates.length > 0 ? ing.clinpgx_candidates.join(', ') : 'multiple'} (not openable)
                    </div>
                  ) : (
                    <div className="ingredient-unmatched">
                      Not matched in ClinPGx
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );

  return (
    <div className="brand-lookup-view" role="region" aria-label="Brand Lookup Results">
      {/* 1. Header with badge */}
      <div className="edge-card card-brand-header">
        <div className="brand-badge-row">
          <span className="brand-source-badge">Brand match (source: NRCeS)</span>
          {total_count > 0 && (
            <span className="brand-count-badge">
              {total_count} {total_count === 1 ? 'product' : 'products'} found
            </span>
          )}
        </div>
        <h3 className="brand-lookup-title">
          Indian Brand Name Lookup (NRCeS)
        </h3>

        {/* 2. Honest Scope / Disclaimer */}
        <div className="brand-scope-banner" role="note">
          <p className="brand-scope-primary">
            This only identifies ingredients. It does not say what the medicine is for or how to take it.
          </p>
          <p className="brand-scope-secondary">
            Lack of ClinPGx records does not mean a medicine is safe.
          </p>
        </div>
      </div>

      {/* 3. Exact Product List */}
      <div className="brand-products-list" role="list">
        {products.map((product) => renderProductCard(product))}
      </div>

      {/* 3b. Similar Products Collapsible */}
      {similar_products && similar_products.length > 0 && (
        <details className="brand-similar-details">
          <summary className="brand-similar-summary">
            Other products with similar names. Check the full name on your pack.
          </summary>
          <div className="brand-similar-list" role="list">
            {similar_products.map((product) => renderProductCard(product))}
          </div>
        </details>
      )}

      {/* 4. Paging */}
      {total_count > limit && (
        <nav className="brand-pagination-controls" aria-label="Brand products pagination">
          <span className="pagination-info">
            Showing {start}-{end} of {total_count} products
          </span>
          <div className="pagination-buttons">
            <button
              type="button"
              className="btn-pagination"
              disabled={offset === 0}
              onClick={() => onPageChange(Math.max(0, offset - limit))}
              aria-label="Previous page of products"
            >
              &larr; Prev
            </button>
            <button
              type="button"
              className="btn-pagination"
              disabled={offset + limit >= total_count}
              onClick={() => onPageChange(offset + limit)}
              aria-label="Next page of products"
            >
              Next &rarr;
            </button>
          </div>
        </nav>
      )}
    </div>
  );
};

export default BrandLookupView;

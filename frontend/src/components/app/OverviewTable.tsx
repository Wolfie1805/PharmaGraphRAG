import React from 'react';
import { OverviewData, OverviewRow } from '../../types';

interface OverviewTableProps {
  overview: OverviewData;
  queryMode: string;
  onOpenPair: (query: string, hints: string[]) => void;
  onLoadMore: () => void;
  loadingMore?: boolean;
}

export const OverviewTable: React.FC<OverviewTableProps> = ({
  overview,
  queryMode,
  onOpenPair,
  onLoadMore,
  loadingMore = false,
}) => {
  const isMedicineOverview = queryMode === 'medicine_overview';
  const entityColHeader = isMedicineOverview ? 'Gene' : 'Medicine';
  const total = overview.total_count || 0;
  const currentCount = overview.rows?.length || 0;
  const hasMore = currentCount < total;

  return (
    <section className="overview-table-section" aria-label="Curated Interactions Table">
      <div className="overview-table-header">
        <div className="overview-title-block">
          <h3 className="overview-heading">
            Curated Interactions ({currentCount} of {total})
          </h3>
          <p className="overview-curation-note">
            These relationship edges and evidence counts represent records cataloged in ClinPGx and PharmGKB archives, not algorithmic predictions.
          </p>
        </div>
      </div>

      <div className="overview-table-container">
        <table className="overview-table" aria-label="Interactions Overview">
          <thead>
            <tr>
              <th scope="col" className="th-entity">{entityColHeader}</th>
              <th scope="col" className="th-assoc">Association</th>
              <th scope="col" className="th-num">Guidelines</th>
              <th scope="col" className="th-num">Drug Labels</th>
              <th scope="col" className="th-num">Annotations</th>
              <th scope="col" className="th-num">Linked Papers</th>
              <th scope="col" className="th-action"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            {(overview.rows || []).map((row: OverviewRow) => {
              const otherName = row.other_name;
              const assocNormalized = (row.association || 'associated').toLowerCase();
              const assocClass =
                assocNormalized === 'associated'
                  ? 'assoc-associated'
                  : assocNormalized === 'not associated'
                  ? 'assoc-not-associated'
                  : 'assoc-ambiguous';

              const pairQuery = `${row.gene_name} ${row.chemical_name}`;
              const hints = [row.gene_id, row.chemical_id];

              return (
                <tr key={`${row.chemical_id}-${row.gene_id}`} className="overview-row">
                  <td className="td-entity">
                    <span className="entity-cell-name">{otherName}</span>
                    <span className="entity-cell-cid font-mono">{row.other_id}</span>
                  </td>
                  <td className="td-assoc">
                    <span className={`assoc-pill ${assocClass}`}>
                      {row.association}
                    </span>
                  </td>
                  <td className="td-num">
                    <span className={row.guideline_count > 0 ? 'count-active' : 'count-zero'}>
                      {row.guideline_count}
                    </span>
                  </td>
                  <td className="td-num">
                    <span className={row.drug_label_count > 0 ? 'count-active' : 'count-zero'}>
                      {row.drug_label_count}
                    </span>
                  </td>
                  <td className="td-num">
                    <span className={row.annotation_count > 0 ? 'count-active' : 'count-zero'}>
                      {row.annotation_count}
                    </span>
                  </td>
                  <td className="td-num">
                    <span className={row.linked_papers_count > 0 ? 'count-active' : 'count-zero'}>
                      {row.linked_papers_count}
                    </span>
                  </td>
                  <td className="td-action">
                    <button
                      type="button"
                      className="btn-open-pair"
                      onClick={() => onOpenPair(pairQuery, hints)}
                      aria-label={`Open detailed findings for ${pairQuery}`}
                    >
                      <span>Open</span>
                      <span aria-hidden="true">&rarr;</span>
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="overview-footer-bar">
        <span className="overview-counter-text">
          Showing {currentCount} of {total} curated entries
        </span>
        <button
          type="button"
          className="btn-show-more"
          disabled={!hasMore || loadingMore}
          onClick={onLoadMore}
        >
          {loadingMore
            ? 'Loading...'
            : hasMore
            ? `Show more (${total - currentCount} remaining)`
            : 'All rows loaded'}
        </button>
      </div>
    </section>
  );
};

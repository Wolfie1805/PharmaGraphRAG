import React from 'react';
import { EvidenceItem } from '../../types';

interface EvidenceChartProps {
  items: EvidenceItem[];
}

interface SourceTypeBar {
  key: string;
  label: string;
  count: number;
  pct: number;
  color: string;
}

export const EvidenceChart: React.FC<EvidenceChartProps> = ({ items = [] }) => {
  const total = items.length;
  if (total === 0) return null;

  const guidelinesCount = items.filter((i) => i.source_type === 'guideline').length;
  const labelsCount = items.filter((i) => i.source_type === 'drug_label').length;
  const annotationsCount = items.filter((i) => i.source_type === 'annotation').length;
  const pubmedCount = items.filter((i) => i.source_type === 'pubmed').length;

  const barData: SourceTypeBar[] = [
    {
      key: 'guideline',
      label: 'Clinical Guidelines',
      count: guidelinesCount,
      pct: Math.round((guidelinesCount / total) * 100),
      color: '#3b82f6',
    },
    {
      key: 'drug_label',
      label: 'Drug Labels',
      count: labelsCount,
      pct: Math.round((labelsCount / total) * 100),
      color: '#10b981',
    },
    {
      key: 'annotation',
      label: 'Variant Annotations',
      count: annotationsCount,
      pct: Math.round((annotationsCount / total) * 100),
      color: '#f59e0b',
    },
    {
      key: 'pubmed',
      label: 'Linked Literature',
      count: pubmedCount,
      pct: Math.round((pubmedCount / total) * 100),
      color: '#8b5cf6',
    },
  ].filter((b) => b.count > 0);

  const datedPapers: { year: number }[] = [];
  items
    .filter((i) => i.source_type === 'pubmed' && i.date)
    .forEach((i) => {
      const match = (i.date || '').match(/\b(19\d\d|20\d\d)\b/);
      if (match) {
        datedPapers.push({ year: parseInt(match[1], 10) });
      }
    });

  const yearCounts: Record<number, number> = {};
  datedPapers.forEach((p) => {
    yearCounts[p.year] = (yearCounts[p.year] || 0) + 1;
  });

  const sortedYears = Object.keys(yearCounts)
    .map(Number)
    .sort((a, b) => a - b);
  const showYearHistogram = datedPapers.length >= 5 && sortedYears.length > 0;
  const maxYearCount = Math.max(...Object.values(yearCounts), 1);

  const barHeight = 24;
  const rowGap = 16;
  const chartHeight = barData.length * (barHeight + rowGap) + 10;
  const svgWidth = 600;
  const labelWidth = 140;
  const maxBarWidth = svgWidth - labelWidth - 90;

  return (
    <div className="evidence-chart-card" aria-label="Evidence Distribution by Source Type">
      <div className="chart-card-header">
        <h4 className="chart-card-title">Evidence Distribution by Source Type</h4>
        <span className="chart-card-subtitle">{total} total items</span>
      </div>

      <div className="chart-svg-container">
        <svg
          viewBox={`0 0 ${svgWidth} ${chartHeight}`}
          className="evidence-bar-svg"
          role="img"
          aria-label="Horizontal bar chart showing distribution of evidence by source type"
        >
          {barData.map((bar, idx) => {
            const y = idx * (barHeight + rowGap) + 10;
            const barWidth = Math.max(4, Math.round((bar.count / total) * maxBarWidth));

            return (
              <g key={bar.key} className="chart-bar-row">
                <text
                  x={labelWidth - 10}
                  y={y + 16}
                  textAnchor="end"
                  className="chart-row-label"
                  fill="#9a9aa0"
                  fontSize="12"
                  fontFamily="var(--font-body)"
                >
                  {bar.label}
                </text>

                <rect
                  x={labelWidth}
                  y={y}
                  width={maxBarWidth}
                  height={barHeight}
                  rx="4"
                  fill="rgba(255, 255, 255, 0.04)"
                />

                <rect
                  x={labelWidth}
                  y={y}
                  width={barWidth}
                  height={barHeight}
                  rx="4"
                  fill={bar.color}
                  opacity="0.85"
                />

                <text
                  x={labelWidth + barWidth + 8}
                  y={y + 16}
                  fill="#f2f2f2"
                  fontSize="12"
                  fontWeight="500"
                  fontFamily="var(--font-body)"
                >
                  {bar.count} ({bar.pct}%)
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {showYearHistogram && (
        <div className="papers-year-histogram" aria-label="Papers Published by Year">
          <div className="histogram-header">
            <span className="histogram-title">Literature Publication Timeline</span>
            <span className="histogram-subtitle">{datedPapers.length} dated papers</span>
          </div>

          <div className="histogram-svg-wrapper">
            <svg
              viewBox={`0 0 ${Math.max(300, sortedYears.length * 48)} 110`}
              className="histogram-svg"
              role="img"
              aria-label="Histogram of publication years for retrieved papers"
            >
              {sortedYears.map((yr, idx) => {
                const count = yearCounts[yr];
                const colWidth = 28;
                const colX = idx * 46 + 16;
                const maxH = 60;
                const barH = Math.max(4, Math.round((count / maxYearCount) * maxH));
                const barY = 80 - barH;

                return (
                  <g key={yr} className="histogram-bar-group">
                    <rect
                      x={colX}
                      y={barY}
                      width={colWidth}
                      height={barH}
                      rx="3"
                      fill="#8b5cf6"
                      opacity="0.8"
                    />
                    <text
                      x={colX + colWidth / 2}
                      y={barY - 4}
                      textAnchor="middle"
                      fill="#f2f2f2"
                      fontSize="10"
                      fontFamily="var(--font-body)"
                    >
                      {count}
                    </text>
                    <text
                      x={colX + colWidth / 2}
                      y="96"
                      textAnchor="middle"
                      fill="#9a9aa0"
                      fontSize="10"
                      fontFamily="var(--font-mono)"
                    >
                      {yr}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
        </div>
      )}
    </div>
  );
};

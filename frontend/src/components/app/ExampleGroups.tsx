import React, { useEffect, useState } from 'react';
import { fetchDemoQuestions } from '../../api';
import { DemoQuestion } from '../../types';

interface ExampleGroupsProps {
  onSelectQuestion: (question: string, hints?: string[]) => void;
  disabled?: boolean;
}

interface CategoryGroup {
  id: string;
  label: string;
  items: DemoQuestion[];
}

const CATEGORY_MAP: Record<string, string> = {
  gene_drug: 'Gene & Medicine',
  variant_drug: 'Variants & Alleles',
  ambiguous_name: 'Ambiguous Entities',
  advice_request: 'Safety & Guardrails',
};

export const ExampleGroups: React.FC<ExampleGroupsProps> = ({ onSelectQuestion, disabled }) => {
  const [questions, setQuestions] = useState<DemoQuestion[]>([]);
  const [activeCategoryId, setActiveCategoryId] = useState<string>('gene_drug');

  useEffect(() => {
    const metaEnv = (import.meta as unknown as { env?: { MODE?: string } }).env;
    if (metaEnv?.MODE === 'test') return;

    let active = true;
    fetchDemoQuestions().then((list) => {
      if (active && list.length > 0) {
        setQuestions(list);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const groups: CategoryGroup[] = Object.entries(CATEGORY_MAP).map(([catId, label]) => {
    return {
      id: catId,
      label,
      items: questions.filter((q) => q.category === catId),
    };
  });

  const activeGroup = groups.find((g) => g.id === activeCategoryId) || groups[0];

  return (
    <div className="example-groups-panel" aria-label="Example Question Groups">
      <div className="example-groups-header">
        <span className="example-groups-title">Example Inquiries</span>
      </div>

      <div className="example-category-tabs" role="tablist" aria-label="Question Categories">
        {groups.map((group) => {
          const isSelected = group.id === activeCategoryId;
          return (
            <button
              key={group.id}
              role="tab"
              aria-selected={isSelected}
              className={`category-tab-pill ${isSelected ? 'is-active' : ''}`}
              onClick={() => setActiveCategoryId(group.id)}
              type="button"
            >
              {group.label}
            </button>
          );
        })}
      </div>

      <div className="example-questions-list" role="tabpanel">
        {activeGroup && activeGroup.items.length > 0 ? (
          activeGroup.items.map((q) => (
            <button
              key={q.id}
              type="button"
              className="example-question-btn"
              disabled={disabled}
              onClick={() => {
                onSelectQuestion(q.question);
              }}
            >
              <span className="example-btn-query">{q.question}</span>
            </button>
          ))
        ) : (
          <div className="example-loading-placeholder">
            Loading example questions...
          </div>
        )}
      </div>
    </div>
  );
};

import React from 'react';
import { useTranslation } from 'react-i18next';
import { SqlCodeBlock } from './SqlCodeBlock';
import { ResultTable } from './ResultTable';
import type { QueryResult } from '../../api/generated/types.gen';
import './AssistantResponseCard.css';

interface AssistantResponseCardProps {
  sql: string;
  result?: QueryResult;
}

export const AssistantResponseCard: React.FC<AssistantResponseCardProps> = ({ sql, result }) => {
  const { t } = useTranslation();

  return (
    <div className="assistant-card-wrapper" data-testid="assistant-response-card">
      <div className="assistant-card">
        <div className="assistant-card-inner">
          <div className="assistant-card-section">
            <h3 className="assistant-card-heading">{t('query.result.sqlHeading')}</h3>
            <SqlCodeBlock code={sql} />
          </div>

          {/* Placeholder action bar — Wave 8.3 */}
          <div className="assistant-card-action-bar-placeholder" data-testid="action-bar-placeholder" />

          {result && (
            <div className="assistant-card-section">
              <h3 className="assistant-card-heading">{t('query.result.tableHeading')}</h3>
              <ResultTable result={result} />
            </div>
          )}

          {/* Placeholder feedback bar — Wave 8.3 */}
          <div className="assistant-card-feedback-bar-placeholder" data-testid="feedback-bar-placeholder" />
        </div>
      </div>
    </div>
  );
};

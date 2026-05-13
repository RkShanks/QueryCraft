import React from 'react';
import { useTranslation } from 'react-i18next';
import { SqlCodeBlock } from './SqlCodeBlock';
import { CodeBlockActionBar } from './CodeBlockActionBar';
import { ResponseFeedbackBar } from './ResponseFeedbackBar';
import { ResultTable } from './ResultTable';
import type { QueryResult } from '../../api/generated/types.gen';
import './AssistantResponseCard.css';

interface AssistantResponseCardProps {
  sql: string;
  result?: QueryResult;
  attemptId?: string;
  currentFeedback?: number | null;
  saved?: boolean;
  onRegenerate?: (attemptId: string) => void;
  onFeedback?: (attemptId: string, feedback: number) => void;
}

export const AssistantResponseCard: React.FC<AssistantResponseCardProps> = ({
  sql,
  result,
  attemptId,
  currentFeedback,
  saved,
  onRegenerate,
  onFeedback,
}) => {
  const { t } = useTranslation();
  const hasActions = !!attemptId && !!onRegenerate && !!onFeedback;

  return (
    <div className="assistant-card-wrapper" data-testid="assistant-response-card">
      <div className="assistant-card">
        <div className="assistant-card-inner">
          <div className="assistant-card-section">
            <h3 className="assistant-card-heading">{t('query.result.sqlHeading')}</h3>
            <SqlCodeBlock code={sql} />
          </div>

          {hasActions && (
            <CodeBlockActionBar
              sql={sql}
              attemptId={attemptId}
              onRegenerate={onRegenerate}
              onFeedback={onFeedback}
            />
          )}

          {result && (
            <div className="assistant-card-section">
              <h3 className="assistant-card-heading">{t('query.result.tableHeading')}</h3>
              <ResultTable result={result} />
            </div>
          )}

          {hasActions && (
            <ResponseFeedbackBar
              attemptId={attemptId}
              currentFeedback={currentFeedback}
              saved={saved}
              onFeedback={onFeedback}
            />
          )}
        </div>
      </div>
    </div>
  );
};

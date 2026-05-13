import React from 'react';
import { useTranslation } from 'react-i18next';
import { SqlCodeBlock } from './SqlCodeBlock';
import { CodeBlockActionBar } from './CodeBlockActionBar';
import { ResultTable } from './ResultTable';
import type { QueryResult } from '../../api/generated/types.gen';
import './AssistantResponseCard.css';

interface AssistantResponseCardProps {
  sql: string;
  result?: QueryResult;
  attemptId?: string;
  saved?: boolean;
  onRegenerate?: (attemptId: string) => void;
  onFeedback?: (attemptId: string, feedback: number) => void;
  onAccept?: (attemptId: string) => void;
  isAccepting?: boolean;
}

export const AssistantResponseCard: React.FC<AssistantResponseCardProps> = ({
  sql,
  result,
  attemptId,
  saved,
  onRegenerate,
  onFeedback,
  onAccept,
  isAccepting,
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

          {result && attemptId && onAccept && !saved && (
            <div className="assistant-card-section assistant-accept-section">
              <button
                className="assistant-accept-btn"
                onClick={() => onAccept(attemptId)}
                disabled={isAccepting}
                data-testid="action-accept"
              >
                {isAccepting ? t('query.actions.accepting') : t('query.actions.accept')}
              </button>
            </div>
          )}

          {result && saved && (
            <div className="assistant-card-section assistant-accepted-banner" data-testid="accepted-banner">
              <span>{t('query.actions.accepted')}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

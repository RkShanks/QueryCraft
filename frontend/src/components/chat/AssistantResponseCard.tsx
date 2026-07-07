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
  savedQueryId?: string;
  connectionName?: string;
  databaseType?: string;
  onRegenerate?: (attemptId: string) => void;
  onDelete?: (savedQueryId: string) => void;
}

export const AssistantResponseCard: React.FC<AssistantResponseCardProps> = ({
  sql,
  result,
  attemptId,
  savedQueryId,
  connectionName,
  databaseType,
  onRegenerate,
  onDelete,
}) => {
  const { t } = useTranslation();
  const hasSqlActions = sql.trim().length > 0;
  const hasMeta = !!connectionName && !!databaseType;

  const typeLabelKey = databaseType
    ? `query.result.databaseType.${databaseType}`
    : undefined;
  const typeLabel = typeLabelKey && t(typeLabelKey) !== typeLabelKey
    ? t(typeLabelKey)
    : databaseType;

  return (
    <div className="assistant-card-wrapper" data-testid="assistant-response-card">
      <div className="assistant-card">
        <div className="assistant-card-inner">
          {hasMeta && (
            <div className="assistant-card-meta" data-testid="connection-metadata">
              <span className="assistant-card-meta-name">{connectionName}</span>
              <span className="assistant-card-meta-badge">{typeLabel}</span>
            </div>
          )}

          <div className="assistant-card-section">
            <h3 className="assistant-card-heading">{t('query.result.sqlHeading')}</h3>
            <SqlCodeBlock code={sql} />
          </div>

          {hasSqlActions && (
            <CodeBlockActionBar
              sql={sql}
              attemptId={attemptId}
              onRegenerate={onRegenerate}
            />
          )}

          {result && (
            <div className="assistant-card-section">
              <h3 className="assistant-card-heading">{t('query.result.tableHeading')}</h3>
              <ResultTable result={result} />
            </div>
          )}

          {savedQueryId && onDelete && (
            <div className="assistant-card-section assistant-delete-section">
              <button
                className="assistant-delete-btn"
                onClick={() => onDelete(savedQueryId)}
                data-testid="action-delete-result"
                aria-label={t('query.actions.deleteResult')}
              >
                {t('query.actions.deleteResult')}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

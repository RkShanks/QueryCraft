import { useTranslation } from 'react-i18next';
import { ResultTable } from '../chat/ResultTable';
import type { AcceptedQueryDetail, QueryResult } from '../../api/generated/types.gen';

export interface HistoryDetailProps {
  item: AcceptedQueryDetail | null;
  isLoading?: boolean;
  error?: Error | null;
}

export const HistoryDetail: React.FC<HistoryDetailProps> = ({ item, isLoading, error }) => {
  const { t } = useTranslation();
  const getDatabaseTypeLabel = (databaseType?: string | null) => {
    if (!databaseType) return null;
    const key = `query.result.databaseType.${databaseType}`;
    const translated = t(key);
    return translated === key ? databaseType : translated;
  };

  if (error) {
    return (
      <div className="history-detail-error p-6 text-red-600">
        {t('history.error')}
      </div>
    );
  }
  if (isLoading) {
    return (
      <div className="history-detail-loading p-6 text-gray-500">
        {t('history.loading')}
      </div>
    );
  }
  if (!item) {
    return (
      <div className="history-detail-empty p-6 text-gray-500">
        {t('history.detail.empty')}
      </div>
    );
  }

  const historyResult: QueryResult | null =
    item.result_columns && item.result_rows
      ? ({
          kind: 'result',
          attempt_id: item.id,
          question: item.question_text,
          generated_sql: item.generated_sql,
          columns: item.result_columns,
          rows: item.result_rows,
          row_count: item.result_row_count ?? 0,
          attempt_number: 1,
          is_last_auto_retry: false,
          accepted_query_id: item.id,
        } as QueryResult)
      : null;

  return (
    <article className="history-detail p-6 space-y-4" data-testid="history-detail">
      {item.database_connection_name && item.database_type && (
        <div className="history-detail-meta" data-testid="history-detail-meta">
          <span className="history-detail-meta-badge inline-flex items-center gap-2">
            <span>{item.database_connection_name}</span>
            <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
              {getDatabaseTypeLabel(item.database_type)}
            </span>
          </span>
        </div>
      )}
      <section>
        <h3 className="text-sm font-medium text-gray-700">
          {t('history.detail.question')}
        </h3>
        <p className="mt-1">{item.question_text}</p>
      </section>
      <section>
        <h3 className="text-sm font-medium text-gray-700">
          {t('history.detail.sql')}
        </h3>
        <pre className="mt-1 bg-gray-50 p-3 rounded overflow-x-auto">
          <code>{item.generated_sql}</code>
        </pre>
      </section>
      {historyResult && (
        <section>
          <h3 className="text-sm font-medium text-gray-700">
            {t('query.result.tableHeading')}
          </h3>
          <ResultTable result={historyResult} />
        </section>
      )}
      <section className="flex gap-6 text-sm text-gray-600">
        <div>
          <span className="font-medium">{t('history.detail.llmProvider')}:</span>{' '}
          {item.llm_provider ?? '—'}
        </div>
        <div>
          <span className="font-medium">{t('history.detail.acceptedAt')}:</span>{' '}
          {item.accepted_at ? new Date(item.accepted_at).toLocaleString() : '—'}
        </div>
      </section>
    </article>
  );
};

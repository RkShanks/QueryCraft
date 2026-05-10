import { useTranslation } from 'react-i18next';
import type { AcceptedQuerySummary } from '../../api/generated/types.gen';

export type HistoryItem = AcceptedQuerySummary & { schema?: string };

export interface HistoryDetailProps {
  item: HistoryItem | null;
  isLoading?: boolean;
  error?: Error | null;
}

export const HistoryDetail: React.FC<HistoryDetailProps> = ({ item, isLoading, error }) => {
  const { t } = useTranslation();

  if (error) {
    return (
      <div className="history-detail-error p-6 text-red-600">
        {t('history.error', { defaultValue: 'Failed to load history.' })}
      </div>
    );
  }
  if (isLoading) {
    return (
      <div className="history-detail-loading p-6 text-gray-500">
        {t('history.loading', { defaultValue: 'Loading…' })}
      </div>
    );
  }
  if (!item) {
    return (
      <div className="history-detail-empty p-6 text-gray-500">
        {t('history.detail.empty', { defaultValue: 'Select an item to view details.' })}
      </div>
    );
  }

  return (
    <article className="history-detail p-6 space-y-4" data-testid="history-detail">
      <section>
        <h3 className="text-sm font-medium text-gray-700">
          {t('history.detail.question', { defaultValue: 'Question' })}
        </h3>
        <p className="mt-1">{item.question_text}</p>
      </section>
      <section>
        <h3 className="text-sm font-medium text-gray-700">
          {t('history.detail.sql', { defaultValue: 'Generated SQL' })}
        </h3>
        <pre className="mt-1 bg-gray-50 p-3 rounded overflow-x-auto">
          <code>{item.generated_sql}</code>
        </pre>
      </section>
      <section className="flex gap-6 text-sm text-gray-600">
        <div>
          <span className="font-medium">{t('history.detail.schema', { defaultValue: 'Schema' })}:</span>{' '}
          {item.schema ?? '—'}
        </div>
        <div>
          <span className="font-medium">{t('history.detail.acceptedAt', { defaultValue: 'Accepted at' })}:</span>{' '}
          {item.accepted_at ? new Date(item.accepted_at).toLocaleString() : '—'}
        </div>
      </section>
    </article>
  );
};

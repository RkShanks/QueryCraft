import { useTranslation } from 'react-i18next';
import type { AcceptedQuerySummary } from '../../api/generated/types.gen';

export interface HistoryListProps {
  items: AcceptedQuerySummary[];
  hasMore?: boolean;
  onLoadMore?: () => void;
}

export const HistoryList: React.FC<HistoryListProps> = ({ items, hasMore, onLoadMore }) => {
  const { t } = useTranslation();

  if (items.length === 0) {
    return (
      <div className="history-empty p-8 text-center text-gray-500">
        {t('history.empty', { defaultValue: 'No accepted queries yet' })}
      </div>
    );
  }

  return (
    <div className="history-list flex flex-col gap-4">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t('history.column.question', { defaultValue: 'Question' })}
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t('history.column.sql', { defaultValue: 'SQL' })}
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t('history.column.acceptedAt', { defaultValue: 'Accepted' })}
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-100">
            {items.map((item) => (
              <tr key={item.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {item.question_text}
                </td>
                <td className="px-6 py-4 text-sm text-gray-600 font-mono">
                  <code className="text-xs bg-gray-100 px-2 py-1 rounded">{item.generated_sql}</code>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {item.accepted_at ? new Date(item.accepted_at).toLocaleString() : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {hasMore && onLoadMore && (
        <div className="flex justify-center">
          <button
            onClick={onLoadMore}
            className="px-4 py-2 text-sm font-medium text-indigo-600 bg-white border border-indigo-200 rounded-md hover:bg-indigo-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors"
          >
            {t('history.loadMore', { defaultValue: 'Load more' })}
          </button>
        </div>
      )}
    </div>
  );
};

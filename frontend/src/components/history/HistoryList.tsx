import { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useDebounce } from '../../hooks/useDebounce';
import type { AcceptedQuerySummary } from '../../api/generated/types.gen';

export type HistoryItem = AcceptedQuerySummary;

export interface HistoryListProps {
  items: HistoryItem[];
  total?: number;
  isLoading?: boolean;
  hasMore?: boolean;
  onLoadMore?: () => void;
  onSelect?: (id: string) => void;
}

export const HistoryList: React.FC<HistoryListProps> = ({
  items,
  isLoading,
  hasMore,
  onLoadMore,
  onSelect,
}) => {
  const { t } = useTranslation();
  const [rawFilter, setRawFilter] = useState('');
  const filter = useDebounce(rawFilter, 300);

  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => {
      const aTime = a.accepted_at ? new Date(a.accepted_at).getTime() : 0;
      const bTime = b.accepted_at ? new Date(b.accepted_at).getTime() : 0;
      return bTime - aTime;
    });
  }, [items]);

  const filteredItems = useMemo(() => {
    if (!filter.trim()) return sortedItems;
    const lower = filter.toLowerCase();
    return sortedItems.filter((item) =>
      (item.question_text ?? '').toLowerCase().includes(lower) ||
      (item.generated_sql ?? '').toLowerCase().includes(lower)
    );
  }, [sortedItems, filter]);

  if (isLoading && items.length === 0) {
    return (
      <div className="history-loading p-8 text-center text-gray-500">
        {t('history.loading', { defaultValue: 'Loading history...' })}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="history-empty p-8 text-center text-gray-500">
        {t('history.empty', { defaultValue: 'No history yet — submit a question to get started.' })}
      </div>
    );
  }

  return (
    <div className="history-list flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={rawFilter}
          onChange={(e) => setRawFilter(e.target.value)}
          placeholder={t('history.filter.placeholder', { defaultValue: 'Filter by question or SQL...' })}
          className="w-full max-w-md px-4 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          aria-label={t('history.filter.placeholder', { defaultValue: 'Filter by question or SQL...' })}
        />
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-start text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t('history.column.question', { defaultValue: 'Question' })}
              </th>
              <th className="px-6 py-3 text-start text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t('history.column.sql', { defaultValue: 'SQL' })}
              </th>
              <th className="px-6 py-3 text-start text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t('history.detail.acceptedAt', { defaultValue: 'Accepted at' })}
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-100">
            {filteredItems.map((item) => (
              <tr
                key={item.id}
                data-testid="history-row"
                tabIndex={0}
                className="hover:bg-gray-50 transition-colors cursor-pointer"
                onClick={() => onSelect?.(item.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelect?.(item.id);
                  }
                }}
                aria-label={item.question_text}
              >
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

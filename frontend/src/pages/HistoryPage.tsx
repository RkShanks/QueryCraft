import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useHistory, useHistoryDetail } from '../hooks/useHistory';
import { HistoryList } from '../components/history/HistoryList';
import { HistoryDetail } from '../components/history/HistoryDetail';

export default function HistoryPage() {
  const { t } = useTranslation();
  const { items, isLoading, error, hasNextPage, fetchNextPage } = useHistory();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { item: selectedItem, isLoading: detailLoading, error: detailError } = useHistoryDetail(selectedId);

  return (
    <div id="history-page" className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-6 py-4 shadow-sm">
        <h1 className="text-xl font-bold text-gray-900">
          {t('history.title', { defaultValue: 'Query History' })}
        </h1>
      </header>
      <main className="max-w-7xl mx-auto p-6">
        <div className="flex flex-col lg:flex-row gap-6">
          <div className="flex-1 min-w-0">
            <HistoryList
              items={items}
              isLoading={isLoading}
              hasMore={hasNextPage}
              onLoadMore={fetchNextPage}
              onSelect={setSelectedId}
            />
          </div>
          <div className="flex-1 min-w-0">
            {error ? (
              <div className="p-6 text-red-600">
                {t('history.error', { defaultValue: 'Failed to load history.' })}
              </div>
            ) : (
              <HistoryDetail
                item={selectedItem}
                isLoading={detailLoading}
                error={detailError}
              />
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

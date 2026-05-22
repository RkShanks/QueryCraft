import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useHistory, useHistoryDetail } from '../hooks/useHistory';
import { HistoryList } from '../components/history/HistoryList';
import { HistoryDetail } from '../components/history/HistoryDetail';
import { Sparkles } from 'lucide-react';

export default function HistoryPage() {
  const { t } = useTranslation();
  const { items, isLoading, error, hasNextPage, fetchNextPage } = useHistory();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { item: selectedItem, isLoading: detailLoading, error: detailError } = useHistoryDetail(selectedId);

  return (
    <div id="history-page" className="min-h-screen bg-obsidian-950 text-text-primary flex flex-col">
      <header className="bg-obsidian-900/90 border-b border-obsidian-800 px-6 py-4 shadow-lg backdrop-blur-md sticky top-0 z-40 select-none">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-neon-cyan animate-pulse" />
            <span>{t('history.title')}</span>
          </h1>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6 w-full flex-1 flex flex-col">
        <div className="flex flex-col lg:flex-row gap-6 flex-1 min-h-[calc(100vh-140px)]">
          {/* Left panel: Query history list */}
          <div className="flex-1 lg:max-w-md w-full bg-obsidian-900/50 border border-obsidian-800/80 rounded-2xl p-4 flex flex-col gap-4 shadow-xl backdrop-blur-sm">
            <HistoryList
              items={items}
              isLoading={isLoading}
              hasMore={hasNextPage}
              onLoadMore={fetchNextPage}
              onSelect={setSelectedId}
              selectedId={selectedId}
            />
          </div>

          {/* Right panel: Query detail inspector */}
          <div className="flex-1 bg-obsidian-900/50 border border-obsidian-800/80 rounded-2xl p-6 shadow-xl backdrop-blur-sm relative min-h-[400px]">
            {error ? (
              <div className="p-6 text-red-400 bg-red-500/5 border border-red-500/10 rounded-xl text-center select-none">
                {t('history.error')}
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

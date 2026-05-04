import { useTranslation } from 'react-i18next';
import { useHistory } from '../hooks/useQuerySubmit';
import { HistoryList } from '../components/history/HistoryList';

export default function HistoryPage() {
  const { t } = useTranslation();
  const { data, isLoading } = useHistory();

  return (
    <div id="history-page" className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-6 py-4 shadow-sm">
        <h1 className="text-xl font-bold text-gray-900">
          {t('history.title', { defaultValue: 'Query History' })}
        </h1>
      </header>
      <main className="max-w-5xl mx-auto p-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
          </div>
        ) : (
          <HistoryList items={data?.items ?? []} />
        )}
      </main>
    </div>
  );
}

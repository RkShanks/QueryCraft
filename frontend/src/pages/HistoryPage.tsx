import { useTranslation } from 'react-i18next';

export default function HistoryPage() {
  const { t } = useTranslation();

  return (
    <div id="history-page" className="min-h-screen p-8">
      <h1 className="text-2xl font-bold mb-6">{t('history.title')}</h1>
      <p className="text-gray-500">{t('history.empty')}</p>
      {/* Full history list in US-5 cluster */}
    </div>
  );
}

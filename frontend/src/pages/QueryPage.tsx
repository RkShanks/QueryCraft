import { useTranslation } from 'react-i18next';

export default function QueryPage() {
  const { t } = useTranslation();

  return (
    <div id="query-page" className="min-h-screen p-8">
      <h1 className="text-2xl font-bold mb-6">{t('app.title')}</h1>
      <p className="text-gray-500">{t('query.ask.placeholder')}</p>
      {/* Full query interface in US-1 cluster */}
    </div>
  );
}

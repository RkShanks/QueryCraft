import { useTranslation } from 'react-i18next';

export default function LoginPage() {
  const { t } = useTranslation();

  return (
    <div id="login-page" className="min-h-screen flex items-center justify-center">
      <div className="max-w-md w-full p-8">
        <h1 className="text-2xl font-bold mb-6">{t('auth.signIn.title')}</h1>
        <p className="text-gray-500">{t('app.subtitle')}</p>
        {/* Full form implementation in US-1 cluster */}
      </div>
    </div>
  );
}

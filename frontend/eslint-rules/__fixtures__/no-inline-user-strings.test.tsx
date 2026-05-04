import { useTranslation } from 'react-i18next';

// VIOLATION CASES — these MUST trip the rule
export function BadJSXText() {
  return <h1>Hello world</h1>;
}

export function BadAttribute() {
  return <input placeholder="Enter your name" />;
}

// VALID CASES — these MUST NOT trip the rule
export function GoodJSXText() {
  const { t } = useTranslation();
  return <h1>{t('home.greeting')}</h1>;
}

export function GoodAttribute() {
  const { t } = useTranslation();
  return <input placeholder={t('form.name')} />;
}

export function PunctuationOnly() {
  return <span>:</span>;
}

export function TechnicalString() {
  return <a href="/dashboard">{'/'}</a>;
}

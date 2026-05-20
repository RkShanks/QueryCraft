import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import en from './locales/en.json';
import ar from './locales/ar.json';

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      ar: { translation: ar },
    },
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false, // React already escapes
    },
    detection: {
      order: ['querystring', 'navigator', 'htmlTag'] as const,
    },
    saveMissing: true,
    parseMissingKeyHandler: (key: string) => {
      if (typeof import.meta !== 'undefined' && import.meta.env?.MODE !== 'production') {
        console.warn(`[i18n] Missing translation key: ${key}`);
      }
      return key;
    },
  });

export default i18n;

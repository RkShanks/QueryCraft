import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './locales/en.json';
import ar from './locales/ar.json';
import { applyDocumentLanguage, resolveInitialLanguage } from './i18n/locale';

// The active locale follows one locked precedence chain (IS-GAP-038):
// explicit ?lng= → persisted device preference → navigator → html lang → en.
// Variants such as ar-EG/en-US normalize to ar/en; unsupported values are
// ignored safely. Detection, persistence and direction all live in
// ./i18n/locale so every consumer shares one normalization helper.
const initialLanguage = resolveInitialLanguage();

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ar: { translation: ar },
  },
  lng: initialLanguage,
  fallbackLng: 'en',
  interpolation: {
    escapeValue: false, // React already escapes
  },
  supportedLngs: ['en', 'ar'],
  load: 'languageOnly',
  saveMissing: true,
  parseMissingKeyHandler: (key: string) => {
    if (typeof import.meta !== 'undefined' && import.meta.env?.MODE !== 'production') {
      console.warn(`[i18n] Missing translation key: ${key}`);
    }
    return key;
  },
});

applyDocumentLanguage(initialLanguage);

export default i18n;

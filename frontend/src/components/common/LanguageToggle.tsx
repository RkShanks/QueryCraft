import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Languages } from 'lucide-react';
import {
  APP_LANGUAGES,
  applyDocumentLanguage,
  directionFor,
  normalizeAppLanguage,
  persistLanguage,
  type AppLanguage,
} from '../../i18n/locale';

const LANGUAGE_LABELS: Record<AppLanguage, { native: string; english: string }> = {
  en: { native: 'English', english: 'English' },
  ar: { native: 'العربية', english: 'Arabic' },
};

export interface LanguageToggleProps {
  className?: string;
}

/**
 * Compact accessible EN/Arabic selector shared by the unauthenticated and
 * authenticated shells. A manual change becomes authoritative: it is
 * persisted as the device preference and any stale `?lng=` query value is
 * rewritten so reloads cannot revert it.
 */
export const LanguageToggle: React.FC<LanguageToggleProps> = ({ className }) => {
  const { i18n, t } = useTranslation();
  const [active, setActive] = useState<AppLanguage>(
    normalizeAppLanguage(i18n.resolvedLanguage ?? i18n.language) ?? 'en'
  );

  useEffect(() => {
    // Some hosts (tests) provide a minimal i18n facade without event APIs.
    if (typeof i18n.on !== 'function') return;
    const sync = () => {
      setActive(normalizeAppLanguage(i18n.resolvedLanguage ?? i18n.language) ?? 'en');
    };
    i18n.on('languageChanged', sync);
    return () => {
      if (typeof i18n.off === 'function') i18n.off('languageChanged', sync);
    };
  }, [i18n]);

  const handleChange = (next: AppLanguage) => {
    if (next === active) return;
    // Optimistic: switching must not depend on framework reactivity.
    setActive(next);
    void i18n.changeLanguage(next).then(() => {
      persistLanguage(next);
      applyDocumentLanguage(next);
      // Keep a present lng parameter coherent so stale values never win.
      if (typeof window !== 'undefined' && window.location.search.includes('lng=')) {
        const params = new URLSearchParams(window.location.search);
        params.set('lng', next);
        window.history.replaceState(null, '', `${window.location.pathname}?${params.toString()}`);
      }
    });
  };

  return (
    <div
      role="group"
      aria-label={t('locale.switcher.label')}
      className={`inline-flex items-center gap-1 rounded-xl border border-obsidian-800 bg-obsidian-950/70 p-1 ${className ?? ''}`}
    >
      <Languages className="w-3.5 h-3.5 text-text-muted mx-1" aria-hidden="true" />
      {APP_LANGUAGES.map((language) => {
        const isActive = language === active;
        return (
          <button
            key={language}
            type="button"
            onClick={() => handleChange(language)}
            aria-pressed={isActive}
            aria-label={LANGUAGE_LABELS[language].english}
            className={`px-2 py-1 text-xs font-semibold rounded-lg transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-neon-cyan/40 ${
              isActive ? 'bg-neon-cyan/15 text-neon-cyan' : 'text-text-muted hover:text-text-primary'
            }`}
            dir={directionFor(language)}
          >
            {LANGUAGE_LABELS[language].native}
          </button>
        );
      })}
    </div>
  );
};

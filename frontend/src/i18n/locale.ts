/**
 * Single source of truth for the active UI locale (IS-GAP-038).
 *
 * Supported active locales are normalized `en` (LTR) and `ar` (RTL).
 * Regional variants resolve to their base language: `en-US` → en,
 * `ar-EG`/`ar-SA` → ar. Precedence for the initial language is:
 *
 *   explicit ?lng= → persisted device preference → navigator → html lang → en
 */

export const APP_LANGUAGES = ['en', 'ar'] as const;

export type AppLanguage = (typeof APP_LANGUAGES)[number];

export type LanguageSource = 'query' | 'stored' | 'navigator' | 'html' | 'fallback';

export const LANGUAGE_STORAGE_KEY = 'querycraft.language';

const RTL_LANGUAGES: ReadonlySet<AppLanguage> = new Set<AppLanguage>(['ar']);

/** Normalize a raw language tag to a supported app language, or null. */
export function normalizeAppLanguage(value: string | null | undefined): AppLanguage | null {
  if (!value) return null;
  const lower = value.trim().toLowerCase().replace(/_/g, '-');
  if (!lower) return null;
  if (lower === 'en' || lower.startsWith('en-')) return 'en';
  if (lower === 'ar' || lower.startsWith('ar-')) return 'ar';
  return null;
}

/** Text direction for a normalized app language. */
export function directionFor(language: AppLanguage): 'ltr' | 'rtl' {
  return RTL_LANGUAGES.has(language) ? 'rtl' : 'ltr';
}

function readQueryLanguage(search: string = window.location.search): AppLanguage | null {
  if (typeof window === 'undefined' || !window.location) return null;
  const params = new URLSearchParams(search);
  return normalizeAppLanguage(params.get('lng'));
}

function safeGet(storage: Storage | undefined, key: string): string | null {
  try {
    return storage?.getItem(key) ?? null;
  } catch {
    // Privacy modes and embedded webviews can deny storage access.
    return null;
  }
}

function safeSet(storage: Storage | undefined, key: string, value: string): void {
  try {
    storage?.setItem(key, value);
  } catch {
    // In-memory switching keeps working without persistence.
  }
}

export function getStorage(): Storage | undefined {
  try {
    return typeof window !== 'undefined' ? window.localStorage : undefined;
  } catch {
    return undefined;
  }
}

/** Read the persisted device-level preference, if any. */
export function readStoredLanguage(): AppLanguage | null {
  return normalizeAppLanguage(safeGet(getStorage(), LANGUAGE_STORAGE_KEY));
}

/** Persist the device-level preference. Locale is not identity-sensitive data. */
export function persistLanguage(language: AppLanguage): void {
  safeSet(getStorage(), LANGUAGE_STORAGE_KEY, language);
}

/**
 * Resolve the initial language following the locked precedence chain.
 * A query-string choice is persisted immediately so navigation and reloads
 * keep it even when the parameter later disappears from the URL.
 */
export function resolveInitialLanguage(options?: {
  navigatorLanguages?: readonly string[];
  search?: string;
}): AppLanguage {
  const query = readQueryLanguage(options?.search ?? window.location.search);
  if (query) {
    persistLanguage(query);
    return query;
  }

  const stored = readStoredLanguage();
  if (stored) return stored;

  const candidates: readonly string[] =
    options?.navigatorLanguages ??
    (typeof navigator !== 'undefined'
      ? [...(navigator.languages ?? []), navigator.language]
      : []);
  for (const candidate of candidates) {
    const normalized = normalizeAppLanguage(candidate);
    if (normalized) return normalized;
  }

  const htmlLang = normalizeAppLanguage(
    typeof document !== 'undefined' ? document.documentElement.lang : null
  );
  if (htmlLang) return htmlLang;

  return 'en';
}

/** Reflect the active language on <html> so CSS and AT agree on direction. */
export function applyDocumentLanguage(language: AppLanguage): void {
  if (typeof document === 'undefined') return;
  document.documentElement.lang = language;
  document.documentElement.dir = directionFor(language);
}

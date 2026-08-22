import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  normalizeAppLanguage,
  directionFor,
  readStoredLanguage,
  persistLanguage,
  resolveInitialLanguage,
  type AppLanguage,
} from './locale';

describe('normalizeAppLanguage (IS-GAP-038)', () => {
  it.each(['en', 'en-US', 'en_GB', 'EN'])('resolves %s to English', (value) => {
    expect(normalizeAppLanguage(value)).toBe<AppLanguage>('en');
  });

  it.each(['ar', 'ar-EG', 'ar-SA', 'AR-EG', 'ar-eg'])('resolves %s to Arabic', (value) => {
    expect(normalizeAppLanguage(value)).toBe<AppLanguage>('ar');
  });

  it.each(['fr', 'fr-FR', '', '   ', 'arabic', null, undefined])(
    'ignores unsupported %s',
    (value) => {
      expect(normalizeAppLanguage(value as string | null | undefined)).toBeNull();
    }
  );
});

describe('directionFor (IS-GAP-038)', () => {
  it('maps Arabic to rtl and English to ltr', () => {
    expect(directionFor('ar')).toBe('rtl');
    expect(directionFor('en')).toBe('ltr');
  });
});

function withLocation(search: string, fn: () => void): void {
  const previous = window.location.href;
  window.history.replaceState(null, '', search || '/');
  try {
    fn();
  } finally {
    window.history.replaceState(null, '', previous);
  }
}

describe('language persistence (IS-GAP-038)', () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(() => window.localStorage.clear());

  it('round-trips a persisted preference', () => {
    persistLanguage('ar');
    expect(readStoredLanguage()).toBe('ar');
    persistLanguage('en');
    expect(readStoredLanguage()).toBe('en');
  });

  it('survives localStorage unavailability without breaking', () => {
    const spy = vi.spyOn(window, 'localStorage', 'get').mockImplementation(() => {
      throw new DOMException('denied', 'SecurityError');
    });
    try {
      expect(readStoredLanguage()).toBeNull();
      expect(() => persistLanguage('ar')).not.toThrow();
    } finally {
      spy.mockRestore();
    }
  });
});

describe('resolveInitialLanguage precedence (IS-GAP-038)', () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(() => window.localStorage.clear());

  it('prefers an explicit supported query language over everything else', () => {
    persistLanguage('en');
    withLocation('/history?lng=ar-EG', () => {
      expect(resolveInitialLanguage({ navigatorLanguages: ['en-US'] })).toBe('ar');
    });
  });

  it('persists the query-string choice on first visit', () => {
    withLocation('/history?lng=ar', () => {
      resolveInitialLanguage({ navigatorLanguages: ['en-US'] });
      expect(readStoredLanguage()).toBe('ar');
    });
  });

  it('falls back to the persisted preference when the query param is absent or invalid', () => {
    persistLanguage('ar');
    withLocation('/', () => {
      expect(resolveInitialLanguage({ navigatorLanguages: ['en-US'] })).toBe('ar');
    });
    withLocation('/?lng=zz-XX', () => {
      expect(resolveInitialLanguage({ navigatorLanguages: ['en-US'] })).toBe('ar');
    });
  });

  it('uses navigator languages before the html lang attribute', () => {
    document.documentElement.lang = 'ar';
    withLocation('/', () => {
      expect(resolveInitialLanguage({ navigatorLanguages: ['en-US'] })).toBe('en');
    });
    withLocation('/', () => {
      expect(resolveInitialLanguage({ navigatorLanguages: ['ar-EG'] })).toBe('ar');
    });
  });

  it('reads the html lang attribute before falling back to English', () => {
    document.documentElement.lang = 'ar-SA';
    withLocation('/', () => {
      expect(resolveInitialLanguage({ navigatorLanguages: [] })).toBe('ar');
    });
    document.documentElement.lang = 'de';
    withLocation('/', () => {
      expect(resolveInitialLanguage({ navigatorLanguages: [] })).toBe('en');
    });
  });
});

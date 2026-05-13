import { describe, it, expect, beforeAll } from 'vitest';
import en from '../../src/locales/en.json';
import ar from '../../src/locales/ar.json';

type LocaleRecord = Record<string, unknown>;

function flattenKeys(obj: LocaleRecord, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) => {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      return flattenKeys(v as LocaleRecord, key);
    }
    return [key];
  });
}

describe('i18n key completeness (bidirectional)', () => {
  let enKeys: string[];
  let arKeys: string[];

  beforeAll(() => {
    enKeys = flattenKeys(en);
    arKeys = flattenKeys(ar);
  });

  it('all en.json keys exist in ar.json', () => {
    const missing = enKeys.filter((k) => !arKeys.includes(k));
    if (missing.length > 0) {
      console.error('Missing in ar.json:', missing);
    }
    expect(missing).toEqual([]);
  });

  it('all ar.json keys exist in en.json', () => {
    const extra = arKeys.filter((k) => !enKeys.includes(k));
    if (extra.length > 0) {
      console.error('Extra in ar.json (not in en.json):', extra);
    }
    expect(extra).toEqual([]);
  });
});

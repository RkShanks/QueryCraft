import { describe, it, expect } from 'vitest';
import en from '../../src/locales/en.json';
import ar from '../../src/locales/ar.json';

function flattenKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) => {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      return flattenKeys(v as Record<string, unknown>, key);
    }
    return [key];
  });
}

describe('F-009: ar.json key completeness', () => {
  it('has exactly the same keys as en.json', () => {
    const enKeys = new Set(flattenKeys(en));
    const arKeys = new Set(flattenKeys(ar));

    const missingInAr = [...enKeys].filter((k) => !arKeys.has(k));
    const extraInAr = [...arKeys].filter((k) => !enKeys.has(k));

    expect(missingInAr).toEqual([]);
    expect(extraInAr).toEqual([]);
  });
});

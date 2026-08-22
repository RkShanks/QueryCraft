import { describe, it, expect, vi } from 'vitest';
import { formatDateTime, formatNumber } from './format';

// Fixed instant so assertions are deterministic across time zones that keep
// whole-hour offsets (the CI runner and developers' machines alike).
const INSTANT = '2026-05-11T10:00:00Z';

describe('formatDateTime routes through the active app locale (IS-GAP-038)', () => {
  it('formats English timestamps with the en locale', () => {
    const output = formatDateTime(INSTANT, { language: 'en', timeZone: 'UTC' });
    expect(output).toMatch(/May/);
    expect(output).toMatch(/11/);
  });

  it('formats Arabic timestamps with the ar locale (Arabic-Indic digits)', () => {
    const output = formatDateTime(INSTANT, { language: 'ar', timeZone: 'UTC' });
    expect(output).toMatch(/[\u0660-\u0669]/);
  });

  it('follows a language change instead of the browser locale', () => {
    const english = formatDateTime(INSTANT, { language: 'en', timeZone: 'UTC' });
    const arabic = formatDateTime(INSTANT, { language: 'ar', timeZone: 'UTC' });
    expect(english).not.toEqual(arabic);
  });

  it('returns a safe fallback for invalid values instead of throwing', () => {
    expect(() => formatDateTime('not-a-date')).not.toThrow();
    expect(formatDateTime('not-a-date')).toBe('-');
    expect(formatDateTime(undefined)).toBe('-');
  });

  it('accepts an options-free call for production sites', () => {
    vi.stubGlobal('Intl', Intl);
    expect(typeof formatDateTime(INSTANT)).toBe('string');
    expect(formatDateTime(INSTANT).length).toBeGreaterThan(0);
  });
});

describe('formatNumber routes through the active app locale (IS-GAP-038)', () => {
  it('groups digits in English', () => {
    expect(formatNumber(1234.5, { language: 'en' })).toMatch(/1,234\.5/);
  });

  it('renders Arabic-Indic digits in Arabic', () => {
    expect(formatNumber(1234.5, { language: 'ar' })).toMatch(/[\u0660-\u0669]/);
  });

  it('keeps non-finite input stable', () => {
    expect(formatNumber(Number.NaN)).toBe('-');
  });
});

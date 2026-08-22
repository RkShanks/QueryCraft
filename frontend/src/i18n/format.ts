/**
 * Locale-aware formatting helpers (IS-GAP-038).
 *
 * All production date/number rendering routes through these helpers so the
 * output follows the normalized active app locale instead of the browser
 * locale. SQL, code and identifiers stay LTR at their call sites.
 */

import appI18n from '../i18n';
import { normalizeAppLanguage, type AppLanguage } from './locale';

export interface FormatOptions {
  language?: AppLanguage;
  timeZone?: string;
}

const DATE_TIME_FORMAT_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
};

function activeLanguage(): AppLanguage {
  return normalizeAppLanguage(appI18n.resolvedLanguage ?? appI18n.language) ?? 'en';
}

/** Format an ISO timestamp for the active app locale; invalid values fall back. */
export function formatDateTime(
  value: string | number | Date | null | undefined,
  options?: FormatOptions
): string {
  if (value === null || value === undefined || value === '') return '-';
  const parsed = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(parsed.getTime())) return '-';
  const formatter = new Intl.DateTimeFormat(options?.language ?? activeLanguage(), {
    ...DATE_TIME_FORMAT_OPTIONS,
    ...(options?.timeZone ? { timeZone: options.timeZone } : {}),
  });
  return formatter.format(parsed);
}

/** Format a number for the active app locale; non-finite values fall back. */
export function formatNumber(value: number | null | undefined, options?: FormatOptions): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '-';
  return new Intl.NumberFormat(options?.language ?? activeLanguage()).format(value);
}

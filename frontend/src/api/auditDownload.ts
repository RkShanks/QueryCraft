/**
 * Safe download-metadata handling for audit exports (CHUNK-22 / IS-GAP-034).
 *
 * A server-supplied filename is honored only when the Content-Disposition
 * carries attachment semantics, decodes cleanly (quoted `filename=` or
 * standards-compliant UTF-8 `filename*=`) and matches the strict contractual
 * basename `audit_export_YYYYMMDDTHHMMSSZ.csv|json` whose extension equals the
 * requested export format. Every other case — missing header, CR/LF/NUL, path
 * separators, traversal, bidi/control characters, wrong extension, malformed
 * encoding or excessive length — falls back to a deterministic safe local name,
 * so filter values and actor/resource data can never reach the filesystem.
 */

import type { AuditExportRequest } from './generated/types.gen';

export type AuditExportFormat = NonNullable<AuditExportRequest['format']>;

export const AUDIT_EXPORT_FILENAME_PATTERN =
  /^audit_export_\d{8}T\d{6}Z\.(?:csv|json)$/;

const MAX_FILENAME_LENGTH = 100;

const EXPECTED_MEDIA_TYPES: Record<AuditExportFormat, string> = {
  csv: 'text/csv',
  json: 'application/json',
};

/** Constant-message failure for a download contract violation. */
export class AuditDownloadError extends Error {
  constructor() {
    super('audit_download_contract_violation');
    this.name = 'AuditDownloadError';
  }
}

export interface AuditDownload {
  blob: Blob;
  /** Validated server filename, or the deterministic safe fallback. */
  filename: string;
  /** Base media type of the successful response (already format-checked). */
  mediaType: string;
}

function hasForbiddenCharacters(value: string): boolean {
  // CR/LF/NUL plus Unicode control (Cc) and bidi/format (Cf) characters.
  // eslint-disable-next-line no-control-regex
  if (/[\u0000-\u001F\u007F]/.test(value)) return true;
  if (
    /[\u00AD\u0600-\u0605\u061C\u06DD\u070F\u08E2\u180E\u200B-\u200F\u202A-\u202E\u2060-\u2064\u2066-\u206F\uFEFF\uFFF9-\uFFFB]/.test(
      value
    )
  ) {
    return true;
  }
  return false;
}

function isAcceptableBasename(name: string, format: AuditExportFormat): boolean {
  if (name.length === 0 || name.length > MAX_FILENAME_LENGTH) return false;
  if (name.includes('/') || name.includes('\\')) return false;
  if (name.includes('..')) return false;
  if (hasForbiddenCharacters(name)) return false;
  if (!AUDIT_EXPORT_FILENAME_PATTERN.test(name)) return false;
  return name.endsWith(`.${format}`);
}

/**
 * Parses an RFC 6266/8187 Content-Disposition value into a validated
 * basename, or null when anything about it is not exactly the contractual
 * server filename shape.
 */
export function parseAuditExportFilename(
  disposition: string | null | undefined,
  format: AuditExportFormat
): string | null {
  if (!disposition) return null;
  // eslint-disable-next-line no-control-regex -- CR/LF/NUL are rejected deliberately
  if (/[\r\n\u0000]/.test(disposition)) return null;

  const trimmed = disposition.trim();
  if (!trimmed.toLowerCase().startsWith('attachment')) return null;
  const afterToken = trimmed.slice('attachment'.length);
  if (afterToken.length > 0 && !/^[\s;]/.test(afterToken)) return null;

  const extended = /filename\*=(?:([^']*)')([^']*)'([^;]*)/i.exec(trimmed);
  const plain = /filename=(?:"((?:[^"\\]|\\.)*)"|([^";]+))/i.exec(trimmed);

  let candidate: string | null = null;
  if (extended) {
    const [, charset = '', , encodedValue = ''] = extended;
    if (charset.toUpperCase() !== 'UTF-8') return null;
    let decoded: string;
    try {
      decoded = decodeURIComponent(encodedValue);
    } catch {
      return null;
    }
    candidate = decoded;
  } else if (plain) {
    const quoted = plain[1];
    const token = plain[2];
    candidate =
      quoted !== undefined
        ? quoted.replace(/\\(.)/g, '$1')
        : (token ?? '').trim();
  }

  if (candidate === null) return null;
  if (!isAcceptableBasename(candidate, format)) return null;
  return candidate;
}

/** Deterministic safe local fallback in the exact contractual shape. */
export function safeAuditExportFilename(format: AuditExportFormat): string {
  const now = new Date();
  const stamp =
    `${String(now.getUTCFullYear()).padStart(4, '0')}` +
    `${String(now.getUTCMonth() + 1).padStart(2, '0')}` +
    `${String(now.getUTCDate()).padStart(2, '0')}` +
    'T' +
    `${String(now.getUTCHours()).padStart(2, '0')}` +
    `${String(now.getUTCMinutes()).padStart(2, '0')}` +
    `${String(now.getUTCSeconds()).padStart(2, '0')}` +
    'Z';
  return `audit_export_${stamp}.${format}`;
}

export function expectedAuditExportMediaType(format: AuditExportFormat): string {
  return EXPECTED_MEDIA_TYPES[format];
}

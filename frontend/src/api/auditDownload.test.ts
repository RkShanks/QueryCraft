import { describe, it, expect } from 'vitest';
import {
  AUDIT_EXPORT_FILENAME_PATTERN,
  parseAuditExportFilename,
  safeAuditExportFilename,
} from './auditDownload';

/**
 * CHUNK-22 / IS-GAP-034 — safe Content-Disposition handling for audit exports.
 * Only a server filename that is an attachment, decodes cleanly and matches
 * `audit_export_YYYYMMDDTHHMMSSZ.csv|json` (extension equal to the requested
 * format) is honored; everything else falls back to the deterministic local
 * name so filter values, actor/resource data, traversal, control characters,
 * wrong extensions or malformed encoding can never reach the filesystem.
 */

describe('parseAuditExportFilename (CHUNK-22)', () => {
  it('accepts a well-formed quoted CSV filename', () => {
    expect(
      parseAuditExportFilename(
        'attachment; filename="audit_export_20260823T120000Z.csv"',
        'csv'
      )
    ).toBe('audit_export_20260823T120000Z.csv');
  });

  it('accepts a well-formed JSON filename only for the json format', () => {
    expect(
      parseAuditExportFilename(
        'attachment; filename="audit_export_20260823T120000Z.json"',
        'json'
      )
    ).toBe('audit_export_20260823T120000Z.json');
  });

  it('rejects an extension that does not match the requested format', () => {
    expect(
      parseAuditExportFilename(
        'attachment; filename="audit_export_20260823T120000Z.json"',
        'csv'
      )
    ).toBeNull();
  });

  it('prefers a standards-compliant UTF-8 filename* over filename', () => {
    expect(
      parseAuditExportFilename(
        "attachment; filename*=UTF-8''audit_export_20260823T120001Z.csv; filename=\"audit_export_20260823T120000Z.csv\"",
        'csv'
      )
    ).toBe('audit_export_20260823T120001Z.csv');
  });

  it('decodes percent-encoded UTF-8 filename* values safely', () => {
    expect(
      parseAuditExportFilename(
        "attachment; filename*=UTF-8''audit_export_20260823T120002%31.csv",
        'csv'
      )
    ).toBeNull(); // decodes to a name violating the strict pattern
  });

  it.each([
    ['missing header', null],
    ['inline disposition', 'inline; filename="audit_export_20260823T120000Z.csv"'],
    ['CR injection', 'attachment; filename="audit_export_20260823T12000\r0Z.csv"'],
    ['LF injection', 'attachment; filename="audit_export_20260823T12000\n0Z.csv"'],
    ['NUL byte', 'attachment; filename="audit_export_20260823T1200\x000Z.csv"'],
    ['path separator slash', 'attachment; filename="../audit_export_20260823T120000Z.csv"'],
    ['path separator backslash', 'attachment; filename="..\\audit_export_20260823T120000Z.csv"'],
    ['nested traversal', 'attachment; filename="audit_export_20260823T120000Z/../../evil.csv"'],
    ['wrong extension', 'attachment; filename="audit_export_20260823T120000Z.txt"'],
    ['missing extension', 'attachment; filename="audit_export_20260823T120000Z"'],
    ['non-UTC suffix', 'attachment; filename="audit_export_20260823T120000+02.csv"'],
    ['bidi control character', 'attachment; filename="â€®audit_export_20260823T120000Z.csv"'],
    ['escaped control character', 'attachment; filename="audit_export_20260823T12000\u0007Z.csv"'],
    ['actor data in name', 'attachment; filename="audit_export_admin@corp.com.csv"'],
    ['filter data in name', 'attachment; filename="audit_export_outcome-success_20260823T120000Z.csv"'],
    ['excessive length', `attachment; filename="${'a'.repeat(140)}audit_export_20260823T120000Z.csv"`],
  ])('rejects %s', (_caseName, disposition) => {
    expect(parseAuditExportFilename(disposition as string | null, 'csv')).toBeNull();
  });

  it('rejects malformed percent-encoding in filename*', () => {
    expect(
      parseAuditExportFilename("attachment; filename*=UTF-8''audit_export_%ZZ.csv", 'csv')
    ).toBeNull();
  });

  it('rejects non-UTF-8 charsets in filename*', () => {
    expect(
      parseAuditExportFilename(
        "attachment; filename*=iso-8859-1''audit_export_20260823T120000Z.csv",
        'csv'
      )
    ).toBeNull();
  });

  it('keeps a plain ASCII filename* that matches the pattern', () => {
    expect(
      parseAuditExportFilename("attachment; filename*=utf-8''audit_export_20260823T120003Z.csv", 'csv')
    ).toBe('audit_export_20260823T120003Z.csv');
  });
});

describe('safeAuditExportFilename (CHUNK-22)', () => {
  it('produces the contractual deterministic UTC shape for csv', () => {
    const name = safeAuditExportFilename('csv');
    expect(name).toMatch(AUDIT_EXPORT_FILENAME_PATTERN);
    expect(name.endsWith('.csv')).toBe(true);
  });

  it('produces the contractual deterministic UTC shape for json', () => {
    const name = safeAuditExportFilename('json');
    expect(name.endsWith('.json')).toBe(true);
    expect(AUDIT_EXPORT_FILENAME_PATTERN.test(name)).toBe(true);
  });

  it('uses the real current UTC time in the fallback stamp', () => {
    const before = new Date();
    const name = safeAuditExportFilename('csv');
    const match = /audit_export_(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z\.csv/.exec(name);
    expect(match).not.toBeNull();
    const [, y, mo, d] = match as RegExpExecArray;
    expect(`${y}-${mo}-${d}`).toBe(
      `${before.getUTCFullYear()}` +
        `-${String(before.getUTCMonth() + 1).padStart(2, '0')}` +
        `-${String(before.getUTCDate()).padStart(2, '0')}`
    );
  });
});

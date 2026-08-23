import { describe, it, expect } from 'vitest';
import { searchAuditEntries, exportAuditEntries, getAuditRetention } from './audit';
import { AuditDownloadError } from './auditDownload';
import { server } from '../test/server';
import { http, HttpResponse } from 'msw';
import { ClientContractError } from './responseValidation';

describe('audit API client', () => {
  it('should search audit entries with params', async () => {
    server.use(
      http.get('/api/v1/admin/audit/entries', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('action_type')).toBe('test.action');
        return HttpResponse.json({
          entries: [],
          pagination: {
            page: 1,
            page_size: 50,
            total_entries: 0,
            total_pages: 0,
          },
        });
      })
    );

    const res = await searchAuditEntries({ action_type: 'test.action' });
    expect(res.entries).toEqual([]);
  });

  it('should export audit entries returning validated blob metadata', async () => {
    server.use(
      http.post('/api/v1/admin/audit/export', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body.format).toBe('csv');
        return new HttpResponse('csv,data', {
          headers: {
            'Content-Type': 'text/csv; charset=utf-8',
            'Content-Disposition': 'attachment; filename="audit_export_20260823T120000Z.csv"',
          },
        });
      })
    );

    const download = await exportAuditEntries({ format: 'csv' });
    expect(download.blob).toBeDefined();
    expect(download.blob.constructor.name).toBe('Blob');
    expect(await download.blob.text()).toBe('csv,data');
    expect(download.filename).toBe('audit_export_20260823T120000Z.csv');
    expect(download.mediaType).toBe('text/csv');
  });

  it('should fall back to a safe deterministic name when metadata is absent', async () => {
    server.use(
      http.post('/api/v1/admin/audit/export', () =>
        new HttpResponse('{}', {
          headers: { 'Content-Type': 'application/json; charset=utf-8' },
        })
      )
    );

    const download = await exportAuditEntries({ format: 'json' });
    expect(download.filename).toMatch(/^audit_export_\d{8}T\d{6}Z\.json$/);
    expect(download.mediaType).toBe('application/json');
  });

  it('should reject a successful response whose media type mismatches the request', async () => {
    server.use(
      http.post('/api/v1/admin/audit/export', () =>
        new HttpResponse('<html>not csv</html>', {
          headers: { 'Content-Type': 'text/html' },
        })
      )
    );

    await expect(exportAuditEntries({ format: 'csv' })).rejects.toBeInstanceOf(
      AuditDownloadError
    );
  });

  it('should pass the caller signal through to the generated client unchanged', async () => {
    let captured: AbortSignal | undefined;
    const controller = new AbortController();
    server.use(
      http.post('/api/v1/admin/audit/export', ({ request }) => {
        captured = request.signal;
        return new HttpResponse('csv,data', {
          headers: {
            'Content-Type': 'text/csv',
            'Content-Disposition': 'attachment; filename="audit_export_20260823T120000Z.csv"',
          },
        });
      })
    );

    await exportAuditEntries({ format: 'csv' }, controller.signal);
    expect(captured).toBe(controller.signal);
  });

  it('should get audit retention', async () => {
    server.use(
      http.get('/api/v1/admin/audit/retention', () => {
        return HttpResponse.json({
          retention_months: 24,
          last_purge_at: null,
          purged_count: null,
        });
      })
    );

    const res = await getAuditRetention();
    expect(res.retention_months).toBe(24);
  });

  it.each([
    ['empty', {}],
    ['non-integer retention', { retention_months: 24.5, last_purge_at: null, purged_count: null }],
    ['invalid timestamp', { retention_months: 24, last_purge_at: 'not-a-date', purged_count: 5 }],
    ['negative purge count', { retention_months: 24, last_purge_at: null, purged_count: -1 }],
  ])('rejects a %s retention response', async (_caseName, responseBody) => {
    server.use(
      http.get('/api/v1/admin/audit/retention', () => {
        return HttpResponse.json(responseBody);
      })
    );

    await expect(getAuditRetention()).rejects.toBeInstanceOf(ClientContractError);
  });
});

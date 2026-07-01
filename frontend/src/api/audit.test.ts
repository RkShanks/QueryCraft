import { describe, it, expect } from 'vitest';
import { searchAuditEntries, exportAuditEntries, getAuditRetention } from './audit';
import { server } from '../test/server';
import { http, HttpResponse } from 'msw';

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

  it('should export audit entries', async () => {
    server.use(
      http.post('/api/v1/admin/audit/export', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body.format).toBe('csv');
        return new HttpResponse('csv,data', {
          headers: { 'Content-Type': 'text/csv' },
        });
      })
    );

    const blob = await exportAuditEntries({ format: 'csv' });
    expect(blob).toBeDefined();
    expect(blob.constructor.name).toBe('Blob');
    const text = await blob.text();
    expect(text).toBe('csv,data');
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
});

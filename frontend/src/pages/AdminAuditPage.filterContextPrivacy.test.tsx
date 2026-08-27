import { fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { AdminAuditPage } from './AdminAuditPage';
import { server } from '../test/server';
import { renderWithClient } from '../test/utils';

/** CHUNK-28 production regression: settled audit searches retain no raw filter values. */

const FILTER_CONTEXT = 'opaque-filter-context';

beforeEach(() => {
  vi.spyOn(window.URL, 'createObjectURL').mockReturnValue('blob:mock');
  vi.spyOn(window.URL, 'revokeObjectURL').mockImplementation(() => {});
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  server.use(
    http.get('/api/v1/admin/audit/status', () =>
      HttpResponse.json({ total_entries: 0, last_verification: null })
    ),
    http.get('/api/v1/admin/audit/retention', () =>
      HttpResponse.json({ retention_months: 24, last_purge_at: null, purged_count: null })
    )
  );
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('AdminAuditPage opaque filter retention (CHUNK-28)', () => {
  it('clears raw drafts and retains only context authority after successful settlement', async () => {
    const canary = 'actor-sensitive-canary';
    const searchUrls: string[] = [];
    let contextBody: unknown;
    let exportBody: unknown;
    server.use(
      http.post('/api/v1/admin/audit/filter-context', async ({ request }) => {
        contextBody = await request.json();
        return HttpResponse.json({
          filter_context: FILTER_CONTEXT,
          applied_fields: ['actor_identity'],
          expires_at: '2026-08-27T12:15:00Z',
        });
      }),
      http.get('/api/v1/admin/audit/entries', ({ request }) => {
        searchUrls.push(request.url);
        const page = Number(new URL(request.url).searchParams.get('page') ?? 1);
        return HttpResponse.json({
          entries: new URL(request.url).searchParams.has('filter_context')
            ? [
                {
                  sequence_number: 1,
                  timestamp: '2026-08-27T12:00:00Z',
                  actor_identity: 'safe-display-actor',
                  action_type: 'query.submit',
                  resource_type: 'database',
                  outcome: 'success',
                  context: {},
                },
              ]
            : [],
          pagination: { page, page_size: 10, total_entries: 1, total_pages: 1 },
        });
      }),
      http.post('/api/v1/admin/audit/export', async ({ request }) => {
        exportBody = await request.json();
        return new HttpResponse('{}', {
          headers: {
            'Content-Type': 'application/json',
            'Content-Disposition': 'attachment; filename="audit_export_20260827T120000Z.json"',
          },
        });
      })
    );

    const { queryClient } = renderWithClient(<AdminAuditPage />);
    const actorInput = await screen.findByLabelText('Actor');
    fireEvent.change(actorInput, { target: { value: canary } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => expect(actorInput).toHaveValue(''));
    expect(await screen.findByText('safe-display-actor')).toBeInTheDocument();
    expect(contextBody).toEqual({ actor_identity: canary });
    expect(searchUrls.some((url) => url.includes(FILTER_CONTEXT))).toBe(true);
    expect(searchUrls.some((url) => url.includes(canary))).toBe(false);
    expect(searchUrls.some((url) => url.includes('actor_identity='))).toBe(false);
    expect(screen.getByTestId('audit-applied-filters')).toHaveTextContent(/Actor:\s*Applied/);
    expect(screen.getByTestId('audit-applied-filters')).not.toHaveTextContent(canary);
    expect(document.documentElement.outerHTML).not.toContain(canary);
    expect(JSON.stringify(queryClient.getQueryCache().getAll().map((query) => query.queryKey))).not.toContain(canary);
    expect(JSON.stringify(queryClient.getQueryCache().getAll().map((query) => query.state.data))).not.toContain(canary);

    fireEvent.click(screen.getByRole('button', { name: 'Export JSON' }));
    await waitFor(() => expect(exportBody).toEqual({ format: 'json', filter_context: FILTER_CONTEXT }));
  });

  it('discards a rejected raw draft and keeps the prior unfiltered export authority', async () => {
    const canary = 'rejected-sensitive-canary';
    let exportBody: unknown;
    server.use(
      http.post('/api/v1/admin/audit/filter-context', () =>
        HttpResponse.json(
          { error: 'invalid_filter', message_key: 'error.validation.generic' },
          { status: 422 }
        )
      ),
      http.get('/api/v1/admin/audit/entries', () =>
        HttpResponse.json({
          entries: [],
          pagination: { page: 1, page_size: 10, total_entries: 0, total_pages: 1 },
        })
      ),
      http.post('/api/v1/admin/audit/export', async ({ request }) => {
        exportBody = await request.json();
        return new HttpResponse('{}', { headers: { 'Content-Type': 'application/json' } });
      })
    );

    const { queryClient } = renderWithClient(<AdminAuditPage />);
    const actorInput = await screen.findByLabelText('Actor');
    fireEvent.change(actorInput, { target: { value: canary } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    expect(await screen.findByText('The filters could not be applied. Please enter them again.')).toBeInTheDocument();
    expect(actorInput).toHaveValue('');
    expect(document.documentElement.outerHTML).not.toContain(canary);
    expect(JSON.stringify(queryClient.getQueryCache().getAll())).not.toContain(canary);
    fireEvent.click(screen.getByRole('button', { name: 'Export JSON' }));
    await waitFor(() => expect(exportBody).toEqual({ format: 'json' }));
  });

  it('removes context queries and suppresses late settlement on unmount', async () => {
    let releaseSearch!: () => void;
    const pendingSearch = new Promise<void>((resolve) => {
      releaseSearch = resolve;
    });
    server.use(
      http.post('/api/v1/admin/audit/filter-context', () =>
        HttpResponse.json({
          filter_context: FILTER_CONTEXT,
          applied_fields: ['actor_identity'],
          expires_at: '2026-08-27T12:15:00Z',
        })
      ),
      http.get('/api/v1/admin/audit/entries', async ({ request }) => {
        if (new URL(request.url).searchParams.has('filter_context')) await pendingSearch;
        return HttpResponse.json({
          entries: [],
          pagination: { page: 1, page_size: 10, total_entries: 0, total_pages: 1 },
        });
      })
    );

    const { queryClient, unmount } = renderWithClient(<AdminAuditPage />);
    const actorInput = await screen.findByLabelText('Actor');
    fireEvent.change(actorInput, { target: { value: 'unmount-sensitive-canary' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() =>
      expect(queryClient.getQueryCache().getAll().some((query) => query.queryKey.includes(FILTER_CONTEXT))).toBe(true)
    );

    unmount();
    releaseSearch();
    await waitFor(() =>
      expect(queryClient.getQueryCache().findAll({ queryKey: ['adminAuditEntries'] })).toHaveLength(0)
    );
  });
});

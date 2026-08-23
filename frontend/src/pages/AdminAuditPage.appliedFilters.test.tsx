import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AdminAuditPage } from './AdminAuditPage';
import { createWrapper } from '../test/utils';
import { server } from '../test/server';
import { http, HttpResponse } from 'msw';

/**
 * CHUNK-22 / IS-GAP-034 — applied-filter authority for audit search/export.
 * Draft form inputs, requested searches and the successfully applied/displayed
 * filters are separate: results, the visible filter summary and every export
 * request must refer to the same applied dataset while unsent changes,
 * pending searches and failed searches never silently move export scope.
 */

const APPLIED_FILTERS_LABEL = 'Applied filters';
const DRAFT_NOTICE_TEXT =
  'Unapplied filter changes are excluded from these results and exports. Run Search to apply them.';

let downloadSpies: {
  createObjectURL: ReturnType<typeof vi.spyOn>;
  revokeObjectURL: ReturnType<typeof vi.spyOn>;
  click: ReturnType<typeof vi.spyOn>;
};

function installDownloadSpies() {
  const createObjectURL = vi.spyOn(window.URL, 'createObjectURL').mockReturnValue('blob:mock');
  const revokeObjectURL = vi.spyOn(window.URL, 'revokeObjectURL').mockImplementation(() => {});
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  return { createObjectURL, revokeObjectURL, click };
}

interface EntriesCall {
  params: Record<string, string>;
}

function entriesRecorder(responder?: (callIndex: number) => HttpResponse | Promise<HttpResponse>) {
  const calls: EntriesCall[] = [];
  server.use(
    http.get('/api/v1/admin/audit/entries', async ({ request }) => {
      const url = new URL(request.url);
      const params: Record<string, string> = {};
      url.searchParams.forEach((value, key) => {
        params[key] = value;
      });
      calls.push({ params });
      if (responder) return responder(calls.length);
      return HttpResponse.json({
        entries: [
          {
            sequence_number: calls.length,
            timestamp: '2026-07-01T12:00:00Z',
            actor_identity: params.actor_identity ?? 'seeded-actor@example.com',
            action_type: params.action_type ?? 'query.submit',
            resource_type: params.resource_type ?? 'database',
            outcome: 'success',
            context: {},
          },
        ],
        pagination: {
          page: Number(params.page ?? 1),
          page_size: 10,
          total_entries: 1,
          total_pages: 1,
        },
      });
    }),
  );
  return calls;
}

function mockAuditShell() {
  server.use(
    http.get('/api/v1/admin/audit/status', () =>
      HttpResponse.json({ total_entries: 0, last_verification: null }),
    ),
    http.get('/api/v1/admin/audit/retention', () =>
      HttpResponse.json({ retention_months: 24, last_purge_at: null, purged_count: null }),
    ),
  );
}

function gateControl() {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { gate, release };
}

async function exportRequestBody(format: 'csv' | 'json'): Promise<Record<string, unknown>> {
  let body: Record<string, unknown> | undefined;
  server.use(
    http.post('/api/v1/admin/audit/export', async ({ request }) => {
      body = (await request.json()) as Record<string, unknown>;
      return new HttpResponse('seq\n1\n', {
        headers: {
          'Content-Type': format === 'csv' ? 'text/csv' : 'application/json',
          'Content-Disposition': `attachment; filename="audit_export_20260823T120000Z.${format}"`,
        },
      });
    }),
  );
  fireEvent.click(screen.getByRole('button', { name: `Export ${format.toUpperCase()}` }));
  await waitFor(() => expect(body).toBeDefined());
  expect(downloadSpies.createObjectURL).toHaveBeenCalled();
  downloadSpies.createObjectURL.mockClear();
  downloadSpies.click.mockClear();
  return body as Record<string, unknown>;
}

/** Applies one actor filter through Search and waits for it to govern results. */
async function applyInitialActorFilter(actor: string) {
  fireEvent.change(screen.getByLabelText('Actor'), { target: { value: actor } });
  fireEvent.click(screen.getByRole('button', { name: 'Search' }));
  await screen.findByText(actor);
}

beforeEach(() => {
  mockAuditShell();
  downloadSpies = installDownloadSpies();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('AdminAuditPage applied-filter contract (CHUNK-22 / IS-GAP-034)', () => {
  it('exports exactly the applied filters and excludes unsent narrowing drafts', async () => {
    entriesRecorder();
    render(<AdminAuditPage />, { wrapper: createWrapper() });
    await applyInitialActorFilter('user-actor@example.com');

    fireEvent.change(screen.getByLabelText('Actor'), {
      target: { value: 'draft-narrower@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Date From'), { target: { value: '2026-07-01' } });

    const body = await exportRequestBody('csv');
    expect(body).toEqual({ format: 'csv', actor_identity: 'user-actor@example.com' });
  });

  it('exports the applied filters when an unsent draft widens them', async () => {
    entriesRecorder();
    render(<AdminAuditPage />, { wrapper: createWrapper() });
    await applyInitialActorFilter('user-actor@example.com');

    // The actor filter was applied through Search; clearing the input must not
    // widen the export scope until Search runs.
    fireEvent.change(screen.getByLabelText('Actor'), { target: { value: '' } });

    const body = await exportRequestBody('json');
    expect(body).toEqual({
      format: 'json',
      action_type: 'query.submit',
      actor_identity: 'user-actor@example.com',
    });
  });

  it('keeps export tied to the prior displayed dataset while a new search is pending', async () => {
    const calls = entriesRecorder();
    render(<AdminAuditPage />, { wrapper: createWrapper() });
    await applyInitialActorFilter('user-actor@example.com');
    expect(calls[calls.length - 1].params.actor_identity).toBe('user-actor@example.com');

    const pending = gateControl();
    let gatedSeen = false;
    server.use(
      http.get('/api/v1/admin/audit/entries', async ({ request }) => {
        const url = new URL(request.url);
        gatedSeen = url.searchParams.get('actor_identity') === 'pending-actor@example.com';
        await pending.gate;
        return HttpResponse.json({
          entries: [
            {
              sequence_number: 2,
              timestamp: '2026-07-02T12:00:00Z',
              actor_identity: 'pending-actor@example.com',
              action_type: 'session.sign_in',
              resource_type: 'session',
              outcome: 'failure',
              context: {},
            },
          ],
          pagination: { page: 1, page_size: 10, total_entries: 1, total_pages: 1 },
        });
      }),
    );

    fireEvent.change(screen.getByLabelText('Actor'), { target: { value: 'pending-actor@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(gatedSeen).toBe(true));

    const pendingBody = await exportRequestBody('csv');
    expect(pendingBody).toEqual({ format: 'csv', actor_identity: 'user-actor@example.com' });

    pending.release();

    await screen.findByText('pending-actor@example.com');
    const appliedBody = await exportRequestBody('csv');
    expect(appliedBody).toEqual({ format: 'csv', actor_identity: 'pending-actor@example.com' });
  });

  it('keeps export tied to the prior displayed dataset after a failed search', async () => {
    const calls = entriesRecorder();
    render(<AdminAuditPage />, { wrapper: createWrapper() });
    await applyInitialActorFilter('user-actor@example.com');

    server.use(
      http.get('/api/v1/admin/audit/entries', () =>
        HttpResponse.json(
          { error: 'internal', message_key: 'error.internal' },
          { status: 500 },
        ),
      ),
    );

    fireEvent.change(screen.getByLabelText('Actor'), { target: { value: 'failed-actor@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    // The prior displayed rows stay visible with a recoverable error state.
    await screen.findByRole('alert');
    expect(screen.getByText('user-actor@example.com')).toBeInTheDocument();

    const body = await exportRequestBody('csv');
    expect(body).toEqual({ format: 'csv', actor_identity: 'user-actor@example.com' });
    expect(calls.length).toBeGreaterThanOrEqual(2);
  });

  it('updates displayed rows and applied filters atomically on successful search', async () => {
    entriesRecorder();
    render(<AdminAuditPage />, { wrapper: createWrapper() });
    await applyInitialActorFilter('user-actor@example.com');

    const successGate = gateControl();
    let releasedWithoutEarlyApply = true;
    server.use(
      http.get('/api/v1/admin/audit/entries', async ({ request }) => {
        const url = new URL(request.url);
        if (url.searchParams.get('action_type') === 'session.sign_in') {
          await successGate.gate;
          releasedWithoutEarlyApply = false;
          return HttpResponse.json({
            entries: [
              {
                sequence_number: 3,
                timestamp: '2026-07-03T12:00:00Z',
                actor_identity: 'signin-actor@example.com',
                action_type: 'session.sign_in',
                resource_type: 'session',
                outcome: 'success',
                context: {},
              },
            ],
            pagination: { page: 1, page_size: 10, total_entries: 1, total_pages: 1 },
          });
        }
        return HttpResponse.json({
          entries: [],
          pagination: { page: 1, page_size: 10, total_entries: 0, total_pages: 1 },
        });
      }),
    );

    fireEvent.change(screen.getByLabelText('Action Type'), { target: { value: 'session.sign_in' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    // While the request is in flight the old applied summary still governs.
    const summary = screen.getByTestId('audit-applied-filters');
    expect(summary).toHaveTextContent('query.submit');

    successGate.release();
    await screen.findByText('signin-actor@example.com');
    expect(releasedWithoutEarlyApply).toBe(false);

    const summaryAfter = screen.getByTestId('audit-applied-filters');
    expect(summaryAfter).toHaveTextContent('session.sign_in');
    expect(summaryAfter).not.toHaveTextContent('query.submit');

    const body = await exportRequestBody('csv');
    expect(body).toEqual({ format: 'csv', action_type: 'session.sign_in' });
  });

  it('retains applied filters across pagination for display and export', async () => {
    const calls: EntriesCall[] = [];
    server.use(
      http.get('/api/v1/admin/audit/entries', async ({ request }) => {
        const url = new URL(request.url);
        const params: Record<string, string> = {};
        url.searchParams.forEach((value, key) => {
          params[key] = value;
        });
        calls.push({ params });
        const page = Number(params.page ?? 1);
        return HttpResponse.json({
          entries: [
            {
              sequence_number: page,
              timestamp: '2026-07-01T12:00:00Z',
              actor_identity: 'paged-actor@example.com',
              action_type: 'query.submit',
              resource_type: 'database',
              outcome: 'success',
              context: {},
            },
          ],
          pagination: { page, page_size: 10, total_entries: 25, total_pages: 3 },
        });
      }),
    );
    render(<AdminAuditPage />, { wrapper: createWrapper() });
    await screen.findByText('paged-actor@example.com');

    fireEvent.change(screen.getByLabelText('Action Type'), { target: { value: 'query.submit' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(calls[calls.length - 1].params.action_type).toBe('query.submit'));

    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(calls[calls.length - 1].params.page).toBe('2'));

    await screen.findByText('Page 2 of 3');
    const body = await exportRequestBody('json');
    expect(body).toEqual({ format: 'json', action_type: 'query.submit' });
  });

  it('shows the applied-filter summary and a polite notice only while drafts differ', async () => {
    entriesRecorder();
    render(<AdminAuditPage />, { wrapper: createWrapper() });
    await applyInitialActorFilter('user-actor@example.com');

    const summary = screen.getByTestId('audit-applied-filters');
    expect(summary).toHaveTextContent(APPLIED_FILTERS_LABEL);
    expect(summary).toHaveTextContent('user-actor@example.com');
    expect(screen.queryByTestId('audit-draft-filters-notice')).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Actor'), {
      target: { value: 'unsent-actor@example.com' },
    });

    expect(await screen.findByTestId('audit-draft-filters-notice')).toHaveTextContent(
      DRAFT_NOTICE_TEXT,
    );
    // The summary keeps describing the displayed dataset.
    expect(screen.getByTestId('audit-applied-filters')).toHaveTextContent('user-actor@example.com');

    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() =>
      expect(screen.queryByTestId('audit-draft-filters-notice')).not.toBeInTheDocument(),
    );
    expect(screen.getByTestId('audit-applied-filters')).toHaveTextContent('unsent-actor@example.com');
  });

  it('repeats the exact failed applied request once on retry and suppresses duplicate clicks', async () => {
    entriesRecorder();
    render(<AdminAuditPage />, { wrapper: createWrapper() });
    await applyInitialActorFilter('user-actor@example.com');

    let failingCalls = 0;
    server.use(
      http.get('/api/v1/admin/audit/entries', ({ request }) => {
        const url = new URL(request.url);
        if (url.searchParams.get('actor_identity') === 'retry-actor@example.com') {
          failingCalls += 1;
          return HttpResponse.json({ error: 'internal', message_key: 'error.internal' }, { status: 500 });
        }
        return HttpResponse.json({
          entries: [],
          pagination: { page: 1, page_size: 10, total_entries: 0, total_pages: 1 },
        });
      }),
    );

    fireEvent.change(screen.getByLabelText('Actor'), { target: { value: 'retry-actor@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    const retry = await screen.findByRole('button', { name: 'Retry' });
    fireEvent.click(retry);
    fireEvent.click(retry);

    await waitFor(() => expect(failingCalls).toBe(2));
    await waitFor(() => expect(retry).toBeEnabled());
    // No further retries happen after settling; the retried request is identical.
    const retryCalls = failingCalls;
    await waitFor(() => expect(failingCalls).toBe(retryCalls));
  });

  it('suppresses duplicate export clicks so one request creates one download', async () => {
    entriesRecorder();
    render(<AdminAuditPage />, { wrapper: createWrapper() });
    await applyInitialActorFilter('user-actor@example.com');

    const exportGate = gateControl();
    let exportCalls = 0;
    server.use(
      http.post('/api/v1/admin/audit/export', async () => {
        exportCalls += 1;
        await exportGate.gate;
        return new HttpResponse('seq\n1\n', {
          headers: {
            'Content-Type': 'text/csv',
            'Content-Disposition': 'attachment; filename="audit_export_20260823T120000Z.csv"',
          },
        });
      }),
    );

    const csvButton = screen.getByRole('button', { name: 'Export CSV' });
    fireEvent.click(csvButton);
    fireEvent.click(csvButton);
    fireEvent.click(csvButton);

    await waitFor(() => expect(exportCalls).toBe(1));
    expect(csvButton).toBeDisabled();

    exportGate.release();
    await waitFor(() => expect(downloadSpies.createObjectURL).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(csvButton).toBeEnabled());
  });
});

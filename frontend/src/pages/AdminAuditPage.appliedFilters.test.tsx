import { fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { AdminAuditPage } from './AdminAuditPage';
import { server } from '../test/server';
import { renderWithClient } from '../test/utils';

/** CHUNK-22 authority regressions carried forward through CHUNK-28 opaque contexts. */

interface ContextCall {
  body: Record<string, unknown>;
  token: string;
}

interface EntriesCall {
  context: string | null;
  page: number;
}

let createObjectUrlSpy: ReturnType<typeof vi.spyOn>;

function mockAuditShell() {
  server.use(
    http.get('/api/v1/admin/audit/status', () =>
      HttpResponse.json({ total_entries: 0, last_verification: null })
    ),
    http.get('/api/v1/admin/audit/retention', () =>
      HttpResponse.json({ retention_months: 24, last_purge_at: null, purged_count: null })
    )
  );
}

function contextRecorder() {
  const calls: ContextCall[] = [];
  server.use(
    http.post('/api/v1/admin/audit/filter-context', async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      const token = `opaque-context-${calls.length + 1}`;
      calls.push({ body, token });
      return HttpResponse.json({
        filter_context: token,
        applied_fields: Object.keys(body),
        expires_at: '2026-08-27T12:15:00Z',
      });
    })
  );
  return calls;
}

function entriesRecorder(responder?: (call: EntriesCall) => Response | Promise<Response>) {
  const calls: EntriesCall[] = [];
  server.use(
    http.get('/api/v1/admin/audit/entries', async ({ request }) => {
      const url = new URL(request.url);
      const call = {
        context: url.searchParams.get('filter_context'),
        page: Number(url.searchParams.get('page') ?? 1),
      };
      calls.push(call);
      if (responder) return responder(call);
      return entriesResponse(call);
    })
  );
  return calls;
}

function entriesResponse(call: EntriesCall): Response {
  return HttpResponse.json({
    entries: [
      {
        sequence_number: call.page,
        timestamp: '2026-07-01T12:00:00Z',
        actor_identity: call.context ? `dataset-${call.context}` : 'dataset-unfiltered',
        action_type: 'query.submit',
        resource_type: 'database',
        outcome: 'success',
        context: {},
      },
    ],
    pagination: { page: call.page, page_size: 10, total_entries: 25, total_pages: 3 },
  });
}

function gateControl() {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { gate, release };
}

async function applyActorFilter(actor: string) {
  await screen.findByText('dataset-unfiltered');
  fireEvent.change(screen.getByLabelText('Actor'), { target: { value: actor } });
  fireEvent.click(screen.getByRole('button', { name: 'Search' }));
  expect(await screen.findByText('dataset-opaque-context-1')).toBeInTheDocument();
}

async function exportRequestBody(format: 'csv' | 'json'): Promise<Record<string, unknown>> {
  let body: Record<string, unknown> | undefined;
  server.use(
    http.post('/api/v1/admin/audit/export', async ({ request }) => {
      body = (await request.json()) as Record<string, unknown>;
      return new HttpResponse(format === 'csv' ? 'seq\n1\n' : '{}', {
        headers: {
          'Content-Type': format === 'csv' ? 'text/csv' : 'application/json',
          'Content-Disposition': `attachment; filename="audit_export_20260827T120000Z.${format}"`,
        },
      });
    })
  );
  fireEvent.click(screen.getByRole('button', { name: `Export ${format.toUpperCase()}` }));
  await waitFor(() => expect(body).toBeDefined());
  expect(createObjectUrlSpy).toHaveBeenCalled();
  createObjectUrlSpy.mockClear();
  return body as Record<string, unknown>;
}

beforeEach(() => {
  mockAuditShell();
  createObjectUrlSpy = vi.spyOn(window.URL, 'createObjectURL').mockReturnValue('blob:mock');
  vi.spyOn(window.URL, 'revokeObjectURL').mockImplementation(() => {});
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('AdminAuditPage applied-filter authority (CHUNK-22 / CHUNK-28)', () => {
  it('exports the settled context and excludes unsent narrowing drafts', async () => {
    const contexts = contextRecorder();
    entriesRecorder();
    const { container } = renderWithClient(<AdminAuditPage />);
    await applyActorFilter('first-sensitive-draft');

    fireEvent.change(screen.getByLabelText('Actor'), { target: { value: 'unsent-sensitive-draft' } });
    expect(await exportRequestBody('csv')).toEqual({ format: 'csv', filter_context: contexts[0].token });
    expect(container.innerHTML).not.toContain('first-sensitive-draft');
  });

  it('keeps export on the prior context while a new search is pending', async () => {
    const contexts = contextRecorder();
    const pending = gateControl();
    entriesRecorder(async (call) => {
      if (call.context === 'opaque-context-2') await pending.gate;
      return entriesResponse({ ...call, page: 1 });
    });
    renderWithClient(<AdminAuditPage />);
    await applyActorFilter('first-sensitive-draft');

    fireEvent.change(screen.getByLabelText('Actor'), { target: { value: 'pending-sensitive-draft' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(contexts).toHaveLength(2));
    expect(await exportRequestBody('json')).toEqual({ format: 'json', filter_context: contexts[0].token });

    pending.release();
    expect(await screen.findByText('dataset-opaque-context-2')).toBeInTheDocument();
    expect(await exportRequestBody('json')).toEqual({ format: 'json', filter_context: contexts[1].token });
  });

  it('keeps the prior dataset and export context after a failed new search', async () => {
    const contexts = contextRecorder();
    entriesRecorder((call) => {
      if (call.context === 'opaque-context-2') {
        return HttpResponse.json({ error: 'internal', message_key: 'error.internal' }, { status: 500 });
      }
      return entriesResponse({ ...call, page: 1 });
    });
    renderWithClient(<AdminAuditPage />);
    await applyActorFilter('first-sensitive-draft');

    fireEvent.change(screen.getByLabelText('Resource Type'), { target: { value: 'failed-sensitive-draft' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await screen.findByRole('alert');
    expect(screen.getByText('dataset-opaque-context-1')).toBeInTheDocument();
    expect(await exportRequestBody('csv')).toEqual({ format: 'csv', filter_context: contexts[0].token });
    expect(document.documentElement.outerHTML).not.toContain('failed-sensitive-draft');
  });

  it('retains the exact context across pagination and export', async () => {
    const contexts = contextRecorder();
    const entries = entriesRecorder();
    renderWithClient(<AdminAuditPage />);
    await applyActorFilter('paged-sensitive-draft');

    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(entries.at(-1)).toEqual({ context: contexts[0].token, page: 2 }));
    expect(await exportRequestBody('json')).toEqual({ format: 'json', filter_context: contexts[0].token });
  });

  it('renders only field labels/status and marks new drafts as unapplied', async () => {
    contextRecorder();
    entriesRecorder();
    renderWithClient(<AdminAuditPage />);
    await applyActorFilter('first-sensitive-draft');

    const summary = screen.getByTestId('audit-applied-filters');
    expect(summary).toHaveTextContent(/Actor:\s*Applied/);
    expect(summary).not.toHaveTextContent('first-sensitive-draft');
    fireEvent.change(screen.getByLabelText('Actor'), { target: { value: 'unsent-sensitive-draft' } });
    expect(await screen.findByTestId('audit-draft-filters-notice')).toBeInTheDocument();
  });

  it('reset returns search and export to the unfiltered authority', async () => {
    contextRecorder();
    const entries = entriesRecorder();
    renderWithClient(<AdminAuditPage />);
    await applyActorFilter('first-sensitive-draft');

    fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
    await waitFor(() => expect(entries.at(-1)?.context).toBeNull());
    await waitFor(() => expect(screen.getByTestId('audit-applied-filters')).toHaveTextContent('All entries'));
    expect(await exportRequestBody('csv')).toEqual({ format: 'csv' });
  });

  it('retries a failed search with the same context and suppresses duplicate clicks', async () => {
    contextRecorder();
    let failingCalls = 0;
    entriesRecorder((call) => {
      if (call.context) {
        failingCalls += 1;
        return HttpResponse.json({ error: 'internal', message_key: 'error.internal' }, { status: 500 });
      }
      return HttpResponse.json({
        entries: [],
        pagination: { page: 1, page_size: 10, total_entries: 0, total_pages: 1 },
      });
    });
    renderWithClient(<AdminAuditPage />);
    await screen.findByText('No audit entries found.');
    fireEvent.change(screen.getByLabelText('Actor'), { target: { value: 'retry-sensitive-draft' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    const retry = await screen.findByRole('button', { name: 'Retry' });
    fireEvent.click(retry);
    fireEvent.click(retry);
    await waitFor(() => expect(failingCalls).toBe(2));
  });

  it('suppresses duplicate export clicks for the settled context', async () => {
    contextRecorder();
    entriesRecorder();
    renderWithClient(<AdminAuditPage />);
    await applyActorFilter('first-sensitive-draft');
    const exportGate = gateControl();
    let exportCalls = 0;
    server.use(
      http.post('/api/v1/admin/audit/export', async () => {
        exportCalls += 1;
        await exportGate.gate;
        return new HttpResponse('seq\n1\n', { headers: { 'Content-Type': 'text/csv' } });
      })
    );

    const button = screen.getByRole('button', { name: 'Export CSV' });
    fireEvent.click(button);
    fireEvent.click(button);
    await waitFor(() => expect(exportCalls).toBe(1));
    exportGate.release();
  });
});

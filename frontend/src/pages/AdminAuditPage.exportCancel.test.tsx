import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AdminAuditPage } from './AdminAuditPage';
import { createWrapper } from '../test/utils';
import { server } from '../test/server';
import { http, HttpResponse } from 'msw';
import { RequestDeadlineError } from '../api/requestScope';

type ExportFn = typeof import('../api/audit').exportAuditEntries;
const exportOverride: { impl?: ExportFn } = {};

vi.mock('../api/audit', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/audit')>();
  return {
    ...actual,
    exportAuditEntries: ((request: Parameters<ExportFn>[0], signal?: AbortSignal) =>
      exportOverride.impl
        ? exportOverride.impl(request, signal)
        : actual.exportAuditEntries(request, signal)) as ExportFn,
  };
});

/**
 * CHUNK-21 / IS-GAP-043 — audit export cancellation and resource lifecycle.
 * Cancel, navigation/unmount and client deadline abort the in-flight export;
 * zero downloads, object URLs or anchors are produced; canceled, timeout and
 * failure states stay localized without raw transport detail.
 */

const CANCEL_LABEL = 'Cancel export';
const CANCELED_TEXT = 'Export canceled.';
const TIMEOUT_TEXT = 'The export took too long and was stopped. Please try again.';

function installDownloadSpies() {
  const createObjectURL = vi.spyOn(window.URL, 'createObjectURL').mockReturnValue('blob:mock');
  const revokeObjectURL = vi.spyOn(window.URL, 'revokeObjectURL').mockImplementation(() => {});
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  return { createObjectURL, revokeObjectURL, click };
}

function mockAuditReads() {
  server.use(
    http.get('/api/v1/admin/audit/status', () =>
      HttpResponse.json({ total_entries: 0, last_verification: null }),
    ),
    http.get('/api/v1/admin/audit/entries', () =>
      HttpResponse.json({
        entries: [],
        pagination: { page: 1, page_size: 10, total_entries: 0, total_pages: 1 },
      }),
    ),
    http.get('/api/v1/admin/audit/retention', () =>
      HttpResponse.json({ retention_months: 24, last_purge_at: null, purged_count: null }),
    ),
  );
}

function gatedExportEndpoint() {
  let captured: AbortSignal | undefined;
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  server.use(
    http.post('/api/v1/admin/audit/export', async ({ request }) => {
      captured = request.signal;
      await gate;
      if (request.signal.aborted) {
        throw new Error('aborted-before-response');
      }
      return HttpResponse.text('seq\n1\n', {
        headers: { 'Content-Type': 'text/csv' },
      });
    }),
  );
  return {
    get signal() {
      return captured;
    },
    async waitForArrival() {
      for (let i = 0; i < 200 && !captured; i += 1) {
        await new Promise((r) => setTimeout(r, 5));
      }
      if (!captured) throw new Error('export request never arrived');
    },
    release,
  };
}

describe('AdminAuditPage export cancellation (CHUNK-21 / IS-GAP-043)', () => {
  let downloadSpies: ReturnType<typeof installDownloadSpies>;

  beforeEach(() => {
    mockAuditReads();
    downloadSpies = installDownloadSpies();
  });

  afterEach(() => {
    exportOverride.impl = undefined;
    vi.restoreAllMocks();
  });

  it('cancel aborts the export with zero downloads and shows a localized canceled state', async () => {
    const gated = gatedExportEndpoint();
    render(<AdminAuditPage />, { wrapper: createWrapper() });
    await screen.findByText('Total Log Entries');

    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }));
    await gated.waitForArrival();

    const cancel = screen.getByRole('button', { name: CANCEL_LABEL });
    fireEvent.click(cancel);

    await waitFor(() => expect(gated.signal?.aborted).toBe(true));
    gated.release();

    expect(await screen.findByText(CANCELED_TEXT)).toBeInTheDocument();
    expect(downloadSpies.createObjectURL).not.toHaveBeenCalled();
    expect(downloadSpies.click).not.toHaveBeenCalled();
    // Export controls become available again after the cancellation settles.
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Export CSV' })).toBeEnabled(),
    );
  });

  it('unmount aborts the in-flight export and produces no resources', async () => {
    const gated = gatedExportEndpoint();
    const { unmount } = render(<AdminAuditPage />, { wrapper: createWrapper() });
    await screen.findByText('Total Log Entries');

    fireEvent.click(screen.getByRole('button', { name: 'Export JSON' }));
    await gated.waitForArrival();

    unmount();
    expect(gated.signal?.aborted).toBe(true);
    gated.release();
    expect(downloadSpies.createObjectURL).not.toHaveBeenCalled();
  });

  it('revokes and removes download resources even when the anchor click fails', async () => {
    server.use(
      http.post('/api/v1/admin/audit/export', () =>
        HttpResponse.text('seq\n1\n', { headers: { 'Content-Type': 'text/csv' } }),
      ),
    );
    downloadSpies.click.mockImplementation(() => {
      throw new Error('synthetic click failure');
    });

    render(<AdminAuditPage />, { wrapper: createWrapper() });
    await screen.findByText('Total Log Entries');

    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }));

    await waitFor(() => expect(downloadSpies.revokeObjectURL).toHaveBeenCalledWith('blob:mock'));
    expect(downloadSpies.createObjectURL).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/unexpected error/i)).toBeInTheDocument();
  });

  it('renders a localized recoverable timeout distinct from generic failures and cancellations', async () => {
    exportOverrideCalls = 0;
    exportOverride.impl = async () => {
      exportOverrideCalls += 1;
      await new Promise((r) => setTimeout(r, 10));
      throw new RequestDeadlineError();
    };

    render(<AdminAuditPage />, { wrapper: createWrapper() });
    await screen.findByText('Total Log Entries');

    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }));

    expect(await screen.findByText(TIMEOUT_TEXT)).toBeInTheDocument();
    expect(downloadSpies.createObjectURL).not.toHaveBeenCalled();
    expect(exportOverrideCalls).toBe(1);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Export CSV' })).toBeEnabled(),
    );
  });
});

let exportOverrideCalls = 0;

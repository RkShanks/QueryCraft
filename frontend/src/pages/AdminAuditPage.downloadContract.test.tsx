import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AdminAuditPage } from './AdminAuditPage';
import { createWrapper } from '../test/utils';
import { server } from '../test/server';
import { http, HttpResponse } from 'msw';

/**
 * CHUNK-22 / IS-GAP-034 — page-level download contract. The browser sees only
 * fully validated downloads: a valid server filename is honored exactly,
 * while media-type violations, permission failures and network failures
 * produce zero files, object URLs or anchors alongside localized recoverable
 * states. Cancel/timeout/quota/422/duplicate behavior keeps its CHUNK-21
 * guarantees under the new metadata contract.
 */

const FAILED_TEXT = 'Export failed. Please try again.';

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

let downloadSpies: ReturnType<typeof installDownloadSpies>;

beforeEach(() => {
  mockAuditReads();
  downloadSpies = installDownloadSpies();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('AdminAuditPage download contract (CHUNK-22 / IS-GAP-034)', () => {
  it('names the download exactly after a valid server filename', async () => {
    server.use(
      http.post('/api/v1/admin/audit/export', () =>
        HttpResponse.text('seq\n1\n', {
          headers: {
            'Content-Type': 'text/csv; charset=utf-8',
            'Content-Disposition': 'attachment; filename="audit_export_20260823T101500Z.csv"',
          },
        }),
      ),
    );
    const setAttribute = vi.spyOn(HTMLAnchorElement.prototype, 'setAttribute');
    render(<AdminAuditPage />, { wrapper: createWrapper() });
    await screen.findByRole('button', { name: 'Export CSV' });

    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }));

    await waitFor(() => expect(downloadSpies.createObjectURL).toHaveBeenCalledTimes(1));
    expect(setAttribute).toHaveBeenCalledWith('download', 'audit_export_20260823T101500Z.csv');
    expect(downloadSpies.revokeObjectURL).toHaveBeenCalledWith('blob:mock');
  });

  it('creates zero download resources when the media type violates the contract', async () => {
    server.use(
      http.post('/api/v1/admin/audit/export', () =>
        new HttpResponse('<html>not csv</html>', {
          headers: { 'Content-Type': 'text/html' },
        }),
      ),
    );
    render(<AdminAuditPage />, { wrapper: createWrapper() });
    await screen.findByRole('button', { name: 'Export CSV' });

    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }));

    expect(await screen.findByText(FAILED_TEXT)).toBeInTheDocument();
    expect(downloadSpies.createObjectURL).not.toHaveBeenCalled();
    expect(downloadSpies.click).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Export CSV' })).toBeEnabled(),
    );
  });

  it.each([
    ['unauthorized', 401],
    ['forbidden', 403],
  ])('survives a %s export response with zero downloads and recoverable controls', async (_name, status) => {
    server.use(
      http.post('/api/v1/admin/audit/export', () =>
        HttpResponse.json(
          { error: 'forbidden', message_key: 'error.forbidden' },
          { status: status as number },
        ),
      ),
    );
    render(<AdminAuditPage />, { wrapper: createWrapper() });
    await screen.findByRole('button', { name: 'Export JSON' });

    fireEvent.click(screen.getByRole('button', { name: 'Export JSON' }));

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Export JSON' })).toBeEnabled(),
    );
    expect(downloadSpies.createObjectURL).not.toHaveBeenCalled();
    expect(screen.queryByTestId('audit-applied-filters')).toBeInTheDocument();
  });

  it('recovers from a mid-flight network failure with zero partial downloads', async () => {
    server.use(
      http.post('/api/v1/admin/audit/export', () => HttpResponse.error()),
    );
    render(<AdminAuditPage />, { wrapper: createWrapper() });
    await screen.findByRole('button', { name: 'Export CSV' });

    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }));

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Export CSV' })).toBeEnabled(),
    );
    expect(downloadSpies.createObjectURL).not.toHaveBeenCalled();
    expect(downloadSpies.revokeObjectURL).not.toHaveBeenCalled();
  });
});

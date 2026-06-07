import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { AdminAuditPage } from './AdminAuditPage';
import { createWrapper } from '../test/utils';
import { server } from '../test/server';
import { http, HttpResponse, delay } from 'msw';

describe('AdminAuditPage', () => {
  it('should display page title and handle empty/never-verified status', async () => {
    server.use(
      http.get('/api/v1/admin/audit/status', () => {
        return HttpResponse.json({
          total_entries: 0,
          last_verification: null,
        });
      })
    );

    render(<AdminAuditPage />, { wrapper: createWrapper() });

    expect(screen.getByText('Tamper-Evident Audit Log Verification')).toBeInTheDocument();
    
    // Total entries display
    expect(await screen.findByText(/Total Log Entries/i)).toBeInTheDocument();
    expect(screen.getByText('0')).toBeInTheDocument();

    // Never verified status
    expect(screen.getByText(/Never verified/i)).toBeInTheDocument();
  });

  it('should display verified intact status correctly', async () => {
    server.use(
      http.get('/api/v1/admin/audit/status', () => {
        return HttpResponse.json({
          total_entries: 42,
          last_verification: {
            verified: true,
            entries_checked: 40,
            first_break_at: null,
            verified_at: '2026-06-07T10:30:00Z',
          },
        });
      })
    );

    render(<AdminAuditPage />, { wrapper: createWrapper() });

    expect(await screen.findByText(/Verified Intact/i)).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText(/Entries checked/i)).toBeInTheDocument();
    expect(screen.getByText('40')).toBeInTheDocument();
  });

  it('should display chain broken status with warning and no repair options', async () => {
    server.use(
      http.get('/api/v1/admin/audit/status', () => {
        return HttpResponse.json({
          total_entries: 100,
          last_verification: {
            verified: false,
            entries_checked: 85,
            first_break_at: 86,
            verified_at: '2026-06-07T12:00:00Z',
          },
        });
      })
    );

    render(<AdminAuditPage />, { wrapper: createWrapper() });

    // Wait for the status query to finish by checking for total entries value
    expect(await screen.findByText('100')).toBeInTheDocument();

    expect(screen.getAllByText(/Chain Broken/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/First break at sequence number/i)).toBeInTheDocument();

    expect(screen.getByText('86')).toBeInTheDocument();

    // Confirm warning description and no auto-repair warning are shown
    expect(screen.getByText(/A hash mismatch was detected/i)).toBeInTheDocument();
    expect(screen.getByText(/No auto-repair utility is provided/i)).toBeInTheDocument();

    // Ensure no dangerous actions like repair/delete/purge are offered
    expect(screen.queryByRole('button', { name: /repair/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /purge/i })).not.toBeInTheDocument();
  });

  it('should handle verification flow and disable button during mutation', async () => {
    server.use(
      http.get('/api/v1/admin/audit/status', () => {
        return HttpResponse.json({
          total_entries: 15,
          last_verification: null,
        });
      })
    );

    let verifyCalled = false;
    server.use(
      http.post('/api/v1/admin/audit/verify', async () => {
        verifyCalled = true;
        await delay(50);
        return HttpResponse.json({
          verified: true,
          entries_checked: 15,
          first_break_at: null,
          verified_at: '2026-06-07T15:00:00Z',
        });
      })
    );

    render(<AdminAuditPage />, { wrapper: createWrapper() });

    // Wait for the status query to finish by checking for total entries value
    expect(await screen.findByText('15')).toBeInTheDocument();

    const verifyBtn = await screen.findByRole('button', { name: /Verify Integrity/i });
    expect(verifyBtn).not.toBeDisabled();

    fireEvent.click(verifyBtn);

    // During pending verification, button should be disabled and show loading state
    await waitFor(() => {
      expect(verifyBtn).toBeDisabled();
      expect(screen.getByText(/Verifying.../i)).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(verifyCalled).toBe(true);
    });

    await waitFor(() => {
      expect(verifyBtn).not.toBeDisabled();
      expect(screen.getByText(/Verify Integrity/i)).toBeInTheDocument();
    });
  });

  it('should display sanitized, generic localized error on failure', async () => {
    server.use(
      http.get('/api/v1/admin/audit/status', () => {
        return HttpResponse.json({
          total_entries: 10,
          last_verification: null,
        });
      })
    );

    server.use(
      http.post('/api/v1/admin/audit/verify', async () => {
        await delay(50);
        return HttpResponse.json({
          detail: 'DATABASE ERROR: SELECT * FROM audit_log WHERE hash = $1; password=secret host=127.0.0.1 port=5432 failed',
        }, { status: 500 });
      })
    );

    render(<AdminAuditPage />, { wrapper: createWrapper() });

    // Wait for the status query to finish by checking for total entries value
    expect(await screen.findByText('10')).toBeInTheDocument();

    const verifyBtn = await screen.findByRole('button', { name: /Verify Integrity/i });
    expect(verifyBtn).not.toBeDisabled();
    fireEvent.click(verifyBtn);

    // Should display the localized generic error message
    expect(await screen.findByText(/Audit chain verification failed/i)).toBeInTheDocument();

    // Make sure no raw backend sql or connection details leaked
    expect(screen.queryByText(/DATABASE ERROR/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/SELECT/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/password/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/127.0.0.1/i)).not.toBeInTheDocument();
  });
});

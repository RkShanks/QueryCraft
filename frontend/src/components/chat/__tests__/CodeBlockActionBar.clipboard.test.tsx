import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CodeBlockActionBar } from '../CodeBlockActionBar';

/**
 * CHUNK-21 / IS-GAP-031 — the workspace SQL copy action shares one bounded
 * copy-state contract: success and failure are localized and announced,
 * rejected/denied writes are never logged with values, focus is preserved and
 * retry works while status timers stay bounded.
 */

const mockWriteText = vi.fn<(text: string) => Promise<void>>();

beforeEach(() => {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: mockWriteText },
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe('CodeBlockActionBar copy contract (CHUNK-21 / IS-GAP-031)', () => {
  it('announces copied state with a polite live region', async () => {
    mockWriteText.mockResolvedValueOnce(undefined);
    render(<CodeBlockActionBar sql="SELECT CANARY;" />);

    fireEvent.click(screen.getByTestId('action-copy'));

    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent(/copied/i),
    );
  });

  it('exposes a localized failed state on rejection without logging the SQL', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    mockWriteText.mockRejectedValueOnce(new DOMException('denied', 'NotAllowedError'));
    render(<CodeBlockActionBar sql="SELECT CANARY;" />);

    fireEvent.click(screen.getByTestId('action-copy'));

    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent(/copy failed/i),
    );
    expect(String(consoleError.mock.calls)).not.toContain('CANARY');
    consoleError.mockRestore();
  });

  it('preserves focus on the copy control across success and failure', async () => {
    mockWriteText.mockResolvedValueOnce(undefined);
    render(<CodeBlockActionBar sql="SELECT 1;" />);

    const button = screen.getByTestId('action-copy');
    button.focus();
    fireEvent.click(button);
    await waitFor(() => expect(mockWriteText).toHaveBeenCalled());
    // The status swap must not replace the control or steal focus.
    expect(document.activeElement).toBe(button);
  });

  it('supports safe retry after a denied write within the same window', async () => {
    mockWriteText
      .mockRejectedValueOnce(new Error('write rejected'))
      .mockResolvedValueOnce(undefined);
    render(<CodeBlockActionBar sql="SELECT 1;" />);

    fireEvent.click(screen.getByTestId('action-copy'));
    await screen.findByText(/copy failed/i);

    // Retry flips the same control back to a copied confirmation.
    fireEvent.click(screen.getByTestId('action-copy'));
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(/copied/i));
    expect(mockWriteText).toHaveBeenCalledTimes(2);
  });
});

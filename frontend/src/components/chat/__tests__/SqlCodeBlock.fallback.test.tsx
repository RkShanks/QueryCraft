import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { SqlCodeBlock } from '../SqlCodeBlock';
import { createWrapper } from '../../../test/utils';

/**
 * CHUNK-21 / IS-GAP-031 — a rejected lazy Shiki chunk must never take down the
 * route or produce an unhandled rejection. The block falls back to readable
 * localized plain-text LTR SQL and announces highlighting unavailability
 * without raw import/chunk details.
 */

// The chunk-load failure itself must be survivable: the factory throws only
// when the lazy import executes.
vi.mock('../ShikiHighlighter', () => {
  throw new Error('Failed to fetch dynamically imported module: qc21-chunk');
});

describe('SqlCodeBlock lazy highlighting failure', () => {
  it('falls back to plain-text SQL with a polite notice when the lazy import rejects', async () => {
    const unhandled: unknown[] = [];
    const handler = (event: PromiseRejectionEvent) => unhandled.push(event.reason);
    window.addEventListener('unhandledrejection', handler);
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(<SqlCodeBlock code="SELECT qc21_secret FROM t;" />, { wrapper: createWrapper() });

    fireEvent.click(screen.getByTestId('sql-toggle-btn'));

    // The raw code remains readable as plain text.
    expect(await screen.findByText('SELECT qc21_secret FROM t;')).toBeInTheDocument();
    // A polite localized status announces unavailability without chunk detail.
    const status = screen.getByRole('status');
    expect(status).toHaveTextContent(/highlighting/i);
    expect(status.textContent).not.toMatch(/chunk|import|ShikiHighlighter/i);
    // The route did not crash: the toggle is still interactive and no alert boundary fired.
    expect(screen.getByTestId('sql-toggle-btn')).toBeInTheDocument();
    await waitFor(() => expect(unhandled).toEqual([]));

    window.removeEventListener('unhandledrejection', handler);
    consoleError.mockRestore();
  });
});

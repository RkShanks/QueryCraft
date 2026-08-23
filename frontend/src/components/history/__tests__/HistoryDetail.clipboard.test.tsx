import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { HistoryDetail } from '../HistoryDetail';

/**
 * CHUNK-21 / IS-GAP-031 — the history detail copy action shares one bounded
 * copy-state contract: success and failure are localized and announced,
 * rejection is never logged with values, and retry works within one window.
 */

const sample = {
  id: 'abc-123',
  question_text: 'Total customers?',
  generated_sql: 'SELECT CANARY_SQL FROM customer',
  accepted_at: '2026-05-11T10:00:00Z',
  llm_provider: 'openai',
  database_connection_id: 'conn-1',
  database_connection_name: 'Production PG',
  database_type: 'postgresql' as const,
};

function setup() {
  return render(
    <MemoryRouter>
      <HistoryDetail item={sample} />
    </MemoryRouter>,
  );
}

function installClipboard(writeText: (text: string) => Promise<void>) {
  const original = navigator.clipboard;
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText },
    writable: true,
    configurable: true,
  });
  return () => {
    Object.defineProperty(navigator, 'clipboard', {
      value: original,
      writable: true,
      configurable: true,
    });
  };
}

describe('HistoryDetail copy contract (CHUNK-21 / IS-GAP-031)', () => {
  let restoreClipboard: () => void;

  beforeEach(() => {
    restoreClipboard = installClipboard(vi.fn().mockResolvedValue(undefined));
  });

  afterEach(() => {
    restoreClipboard();
    vi.restoreAllMocks();
  });

  it('announces copied state and returns to idle within the bounded window', async () => {
    setup();
    const button = screen.getByRole('button', { name: /copy sql/i });
    fireEvent.click(button);

    expect(await screen.findByRole('button', { name: /copied/i })).toBeInTheDocument();

    // The confirmation returns to idle within its bounded window.
    await waitFor(
      () => expect(screen.getByRole('button', { name: /copy sql/i })).toBeInTheDocument(),
      { timeout: 2_500 },
    );
  });

  it('shows a localized failure on rejection without logging the SQL value', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    restoreClipboard = installClipboard(
      vi.fn().mockRejectedValue(new DOMException('denied', 'NotAllowedError')),
    );
    setup();
    fireEvent.click(screen.getByRole('button', { name: /copy sql/i }));

    expect(await screen.findByRole('button', { name: /copy failed/i })).toBeInTheDocument();
    expect(String(consoleError.mock.calls)).not.toContain('CANARY_SQL');
    consoleError.mockRestore();
  });

  it('supports safe retry after a denied write', async () => {
    const writeText = vi
      .fn<(text: string) => Promise<void>>()
      .mockRejectedValueOnce(new Error('write rejected'))
      .mockResolvedValueOnce(undefined);
    restoreClipboard = installClipboard(writeText);
    setup();

    fireEvent.click(screen.getByRole('button', { name: /copy sql/i }));
    await screen.findByRole('button', { name: /copy failed/i });

    fireEvent.click(screen.getByRole('button', { name: /copy failed/i }));
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /copied/i })).toBeInTheDocument(),
    );
    expect(writeText).toHaveBeenCalledTimes(2);
  });
});

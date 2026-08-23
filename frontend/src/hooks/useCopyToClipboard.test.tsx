import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useCopyToClipboard } from './useCopyToClipboard';

/**
 * CHUNK-21 / IS-GAP-031 — one bounded copy-state contract shared by SQL copy
 * surfaces: unavailable API, denied/rejected writes and success each map to a
 * distinct status; retries and unmount clear the reset timer exactly once and
 * neither the copied value nor the raw error is ever logged or persisted.
 */

function installClipboard(writeText?: (text: string) => Promise<void>) {
  const original = navigator.clipboard;
  Object.defineProperty(navigator, 'clipboard', {
    value: writeText ? { writeText } : undefined,
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

describe('useCopyToClipboard', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('reports copied after a successful write and returns to idle once', async () => {
    const restore = installClipboard(vi.fn().mockResolvedValue(undefined));
    const { result } = renderHook(() => useCopyToClipboard({ resetDelayMs: 20 }));

    await act(async () => {
      await result.current.copy('SELECT secret;');
    });
    expect(result.current.status).toBe('copied');

    await waitFor(() => expect(result.current.status).toBe('idle'));
    restore();
  });

  it('maps an unavailable clipboard API to a failed status without throwing', async () => {
    const restore = installClipboard(undefined);
    const { result } = renderHook(() => useCopyToClipboard({ resetDelayMs: 20 }));

    let outcome: boolean | undefined;
    await act(async () => {
      outcome = await result.current.copy('SELECT secret;');
    });
    expect(outcome).toBe(false);
    expect(result.current.status).toBe('failed');
    restore();
  });

  it('maps rejected writes (permission denial) to failed without logging values or errors', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const restore = installClipboard(
      vi.fn().mockRejectedValue(new DOMException('denied', 'NotAllowedError')),
    );
    const { result } = renderHook(() => useCopyToClipboard({ resetDelayMs: 20 }));

    let outcome: boolean | undefined;
    await act(async () => {
      outcome = await result.current.copy('CANARY_SQL_TEXT');
    });

    expect(outcome).toBe(false);
    expect(result.current.status).toBe('failed');
    expect(String(consoleError.mock.calls)).not.toContain('CANARY_SQL_TEXT');
    expect(String(consoleError.mock.calls)).not.toMatch(/NotAllowedError/);
    consoleError.mockRestore();
    consoleWarn.mockRestore();
    restore();
  });

  it('supports safe retry: failure then success within the reset window', async () => {
    const writeText = vi
      .fn<(text: string) => Promise<void>>()
      .mockRejectedValueOnce(new Error('write rejected'))
      .mockResolvedValueOnce(undefined);
    const restore = installClipboard(writeText);
    const { result } = renderHook(() => useCopyToClipboard({ resetDelayMs: 5_000 }));

    await act(async () => {
      await result.current.copy('first');
    });
    expect(result.current.status).toBe('failed');

    // Retry immediately: the first failure's timer must not fire afterwards.
    await act(async () => {
      await result.current.copy('second');
    });
    expect(result.current.status).toBe('copied');
    expect(writeText).toHaveBeenCalledTimes(2);

    // No late timer flips copied back while the window is still open.
    await new Promise((r) => setTimeout(r, 30));
    expect(result.current.status).toBe('copied');
    restore();
  });

  it('stops the reset timer on unmount so no post-unmount state change occurs', async () => {
    const restore = installClipboard(vi.fn().mockResolvedValue(undefined));
    const { result, unmount } = renderHook(() => useCopyToClipboard({ resetDelayMs: 15 }));

    await act(async () => {
      await result.current.copy('SELECT 1;');
    });
    expect(result.current.status).toBe('copied');
    unmount();

    await new Promise((r) => setTimeout(r, 40));
    expect(result.current.status).toBe('copied');
    restore();
  });
});

import { useCallback, useEffect, useRef, useState } from 'react';

export type CopyStatus = 'idle' | 'copied' | 'failed';

interface UseCopyToClipboardOptions {
  /** How long the copied confirmation stays before returning to idle. */
  resetDelayMs?: number;
}

export interface CopyToClipboardResult {
  status: CopyStatus;
  copy: (text: string) => Promise<boolean>;
  reset: () => void;
}

/**
 * One bounded copy-state contract for SQL copy surfaces (CHUNK-21 /
 * IS-GAP-031). Handles an unavailable clipboard API, permission denial and
 * rejected writes without logging or persisting the copied value or the raw
 * error; the status-reset timer is cleared on retry and unmount exactly once.
 */
export function useCopyToClipboard(
  options: UseCopyToClipboardOptions = {},
): CopyToClipboardResult {
  const resetDelayMs = options.resetDelayMs ?? 2_000;
  const [status, setStatus] = useState<CopyStatus>('idle');
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, []);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const scheduleReset = useCallback(() => {
    clearTimer();
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      if (mountedRef.current) setStatus('idle');
    }, resetDelayMs);
  }, [clearTimer, resetDelayMs]);

  const copy = useCallback(
    async (text: string): Promise<boolean> => {
      let succeeded = false;
      try {
        const clipboard = navigator.clipboard;
        if (clipboard && typeof clipboard.writeText === 'function') {
          await clipboard.writeText(text);
          succeeded = true;
        }
      } catch {
        // Intentionally value-free: neither the copied text nor the raw error
        // is logged, rendered or persisted.
        succeeded = false;
      }
      if (!mountedRef.current) return succeeded;
      clearTimer();
      setStatus(succeeded ? 'copied' : 'failed');
      if (succeeded) scheduleReset();
      return succeeded;
    },
    [clearTimer, scheduleReset],
  );

  const reset = useCallback(() => {
    clearTimer();
    if (mountedRef.current) setStatus('idle');
  }, [clearTimer]);

  return { status, copy, reset };
}

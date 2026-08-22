/**
 * Request-scope utility for browser async lifetime (CHUNK-21 / IS-GAP-043).
 *
 * Combines one owned AbortController with an optional parent signal, an
 * optional client deadline, abort classification and exactly-once cleanup of
 * listeners and timers. Browser aborts only ever suppress frontend settlement;
 * they make no claim about server-side work.
 */

export const ORDINARY_REQUEST_TIMEOUT_MS = 15_000;
export const AUDIT_EXPORT_TIMEOUT_MS = 60_000;

export type RequestAbortReason = 'caller' | 'deadline' | 'parent';

export class RequestAbortedError extends Error {
  constructor() {
    super('request_aborted');
    this.name = 'RequestAbortedError';
  }
}

export class RequestDeadlineError extends Error {
  constructor() {
    super('request_deadline_exceeded');
    this.name = 'RequestDeadlineError';
  }
}

const ABORT_ERROR_NAMES = new Set(['AbortError', 'TimeoutError']);

/**
 * True when the failure belongs to the browser-side request lifetime (fetch
 * abort or this utility's typed errors) rather than to server data. Such
 * failures must never render errors, toasts or stale state.
 */
export function isAbortFailure(error: unknown): boolean {
  if (error instanceof RequestAbortedError || error instanceof RequestDeadlineError) {
    return true;
  }
  return error instanceof Error && ABORT_ERROR_NAMES.has(error.name);
}

/** True when this client's own deadline expired. */
export function isClientDeadlineError(error: unknown): boolean {
  return error instanceof RequestDeadlineError;
}

/** True when the request was cancelled intentionally in the browser. */
export function isRequestAbortedError(error: unknown): boolean {
  return isAbortFailure(error) && !isClientDeadlineError(error);
}

export interface RequestScopeOptions {
  /** Parent signal to join; its cancellation forwards as an intentional abort. */
  signal?: AbortSignal | null;
  /** Optional client deadline in milliseconds. */
  timeoutMs?: number;
  /** Called exactly once when the scope first aborts. */
  onAbort?: (reason: RequestAbortReason) => void;
}

export interface DisposableRequestScope {
  readonly signal: AbortSignal;
  readonly aborted: boolean;
  readonly reason: RequestAbortReason | null;
  abort(): void;
  throwIfAborted(): Error | null;
  dispose(): void;
}

export class RequestScope implements DisposableRequestScope {
  readonly signal: AbortSignal;

  private readonly controller = new AbortController();
  private readonly onAbort: (reason: RequestAbortReason) => void;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private parentListener: (() => void) | null = null;
  private parentSignal: AbortSignal | null = null;
  private reason: RequestAbortReason | null = null;
  private notified = false;
  private disposed = false;

  constructor(options: RequestScopeOptions = {}) {
    this.signal = this.controller.signal;
    this.onAbort = options.onAbort ?? (() => {});

    if (options.signal) {
      if (options.signal.aborted) {
        this.fireAbort('parent');
      } else {
        this.parentSignal = options.signal;
        this.parentListener = () => this.fireAbort('parent');
        options.signal.addEventListener('abort', this.parentListener, { once: true });
      }
    }

    if (!this.reason && options.timeoutMs !== undefined && Number.isFinite(options.timeoutMs)) {
      if (options.timeoutMs >= 0) {
        this.timer = setTimeout(() => {
          this.timer = null;
          this.fireAbort('deadline');
        }, options.timeoutMs);
      }
    }
  }

  get aborted(): boolean {
    return this.controller.signal.aborted;
  }

  get reason(): RequestAbortReason | null {
    return this.reason;
  }

  abort(): void {
    this.fireAbort('caller');
  }

  throwIfAborted(): Error | null {
    if (!this.aborted) return null;
    if (this.reason === 'deadline') return new RequestDeadlineError();
    return new RequestAbortedError();
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    if (this.timer !== null) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.parentSignal && this.parentListener) {
      this.parentSignal.removeEventListener('abort', this.parentListener);
      this.parentListener = null;
      this.parentSignal = null;
    }
  }

  private fireAbort(reason: RequestAbortReason): void {
    if (this.reason !== null) return;
    this.reason = reason;
    if (this.timer !== null) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    this.controller.abort();
    if (!this.notified) {
      this.notified = true;
      this.onAbort(reason);
    }
  }
}

export function createRequestScope(options: RequestScopeOptions = {}): DisposableRequestScope {
  return new RequestScope(options);
}

/**
 * Runs one ordinary read/admin request under the single documented bounded
 * network deadline. Parent cancellations keep their native abort error so
 * TanStack Query treats them as silent cancellations; only this client's own
 * deadline expiry is reclassified as {@link RequestDeadlineError}.
 */
export async function withRequestDeadline<T>(
  run: (signal: AbortSignal) => Promise<T>,
  options: { signal?: AbortSignal | null; timeoutMs?: number } = {},
): Promise<T> {
  const scope = new RequestScope({
    signal: options.signal,
    timeoutMs: options.timeoutMs ?? ORDINARY_REQUEST_TIMEOUT_MS,
  });
  try {
    return await run(scope.signal);
  } catch (error) {
    if (scope.reason === 'deadline') {
      throw new RequestDeadlineError();
    }
    throw error;
  } finally {
    scope.dispose();
  }
}

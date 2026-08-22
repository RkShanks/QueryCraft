import { describe, it, expect, vi, afterEach } from 'vitest';
import {
  AUDIT_EXPORT_TIMEOUT_MS,
  ORDINARY_REQUEST_TIMEOUT_MS,
  RequestAbortedError,
  RequestDeadlineError,
  RequestScope,
  createRequestScope,
  isClientDeadlineError,
  isRequestAbortedError,
} from './requestScope';

describe('requestScope', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('documents one bounded ordinary network deadline and a longer audit-export deadline', () => {
    expect(ORDINARY_REQUEST_TIMEOUT_MS).toBeGreaterThan(0);
    expect(AUDIT_EXPORT_TIMEOUT_MS).toBeGreaterThan(ORDINARY_REQUEST_TIMEOUT_MS);
  });

  it('completes without aborting when nothing times out or cancels', async () => {
    using scope = new RequestScope({ timeoutMs: 50 });
    expect(scope.aborted).toBe(false);
    await Promise.resolve();
    expect(scope.signal.aborted).toBe(false);
    scope.dispose();
    expect(scope.aborted).toBe(false);
  });

  it('aborts with the caller reason when the owned controller is aborted', () => {
    const scope = new RequestScope({});
    scope.abort();
    expect(scope.aborted).toBe(true);
    expect(scope.reason).toBe('caller');
    expect(scope.signal.aborted).toBe(true);
    const err = scope.throwIfAborted();
    expect(isRequestAbortedError(err)).toBe(true);
    scope.dispose();
  });

  it('classifies deadline expiry distinctly from an intentional abort', () => {
    vi.useFakeTimers();
    const scope = new RequestScope({ timeoutMs: 1_000 });
    vi.advanceTimersByTime(1_001);
    expect(scope.aborted).toBe(true);
    expect(scope.reason).toBe('deadline');
    const err = scope.throwIfAborted();
    expect(isClientDeadlineError(err)).toBe(true);
    expect(isRequestAbortedError(err)).toBe(false);
    scope.dispose();
  });

  it('forwards parent-signal cancellation as an intentional abort', () => {
    const parent = new AbortController();
    const scope = new RequestScope({ signal: parent.signal });
    parent.abort();
    expect(scope.aborted).toBe(true);
    expect(scope.reason).toBe('caller');
    expect(isRequestAbortedError(scope.throwIfAborted())).toBe(true);
    scope.dispose();
  });

  it('is aborted immediately when the parent signal already aborted', () => {
    const parent = new AbortController();
    parent.abort();
    const scope = new RequestScope({ signal: parent.signal });
    expect(scope.aborted).toBe(true);
    expect(scope.reason).toBe('caller');
    scope.dispose();
  });

  it('stops the deadline timer when the caller aborts first', () => {
    vi.useFakeTimers();
    const timerSpy = vi.fn();
    const scope = new RequestScope({
      timeoutMs: 500,
      onAbort: timerSpy,
    });
    scope.abort();
    vi.advanceTimersByTime(2_000);
    expect(scope.reason).toBe('caller');
    expect(timerSpy).toHaveBeenCalledTimes(1);
    scope.dispose();
    expect(timerSpy).toHaveBeenCalledTimes(1);
  });

  it('notifies through onAbort exactly once regardless of how many causes fire', () => {
    const parent = new AbortController();
    const onAbort = vi.fn();
    const scope = new RequestScope({ signal: parent.signal, onAbort });
    scope.abort();
    parent.abort();
    scope.abort();
    scope.dispose();
    expect(onAbort).toHaveBeenCalledTimes(1);
  });

  it('cleans up parent listeners and timers exactly once across repeated dispose calls', () => {
    const removeEventListenerSpy = vi.spyOn(AbortSignal.prototype, 'removeEventListener');
    vi.useFakeTimers();
    const parent = new AbortController();
    const scope = new RequestScope({ signal: parent.signal, timeoutMs: 5_000 });
    scope.dispose();
    scope.dispose();
    vi.advanceTimersByTime(10_000);
    expect(removeEventListenerSpy).toHaveBeenCalledTimes(1);
    expect(parent.signal.removeEventListener).toHaveBeenCalled();
    removeEventListenerSpy.mockRestore();
  });

  it('never fires the deadline after dispose', () => {
    vi.useFakeTimers();
    const scope = new RequestScope({ timeoutMs: 100 });
    scope.dispose();
    vi.advanceTimersByTime(1_000);
    expect(scope.aborted).toBe(false);
  });

  it('exposes a factory that returns a disposed-safe scope', () => {
    const scope = createRequestScope({ timeoutMs: 10 });
    expect(scope).toBeInstanceOf(RequestScope);
    scope.dispose();
    expect(() => scope.throwIfAborted()).not.toThrow();
  });

  it('keeps typed errors free of transport detail', () => {
    const aborted = new RequestAbortedError();
    const deadline = new RequestDeadlineError();
    expect(aborted.message).toBe('request_aborted');
    expect(deadline.message).toBe('request_deadline_exceeded');
    expect(JSON.stringify(aborted)).not.toContain('fetch');
  });
});

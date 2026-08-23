import { act, renderHook } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { useQuerySubmit } from './useQuerySubmit';
import { createWrapper } from '../test/utils';
import { server } from '../test/server';
import { http, HttpResponse } from 'msw';
import {
  beginSessionDeletion,
  resetSessionDeletionLifecycle,
} from '../sessionDeletionLifecycle';

const RESULT_BODY = {
  kind: 'result',
  attempt_id: 'attempt-1',
  question: 'q',
  generated_sql: 'SELECT 1',
  columns: [{ name: 'one', type: 'integer' }],
  rows: [[1]],
  row_count: 1,
  attempt_number: 1,
  is_last_auto_retry: false,
};

interface PendingRequest {
  readonly signal: AbortSignal | undefined;
  waitForArrival(): Promise<void>;
  release(): void;
}

function gatedEndpoint(paths: string[]): PendingRequest {
  const arrivals: AbortSignal[] = [];
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  for (const path of paths) {
    server.use(
      http.post(path, async ({ request }) => {
        arrivals.push(request.signal);
        await gate;
        return HttpResponse.json(RESULT_BODY);
      }),
    );
  }
  return {
    get signal() {
      return arrivals[0];
    },
    async waitForArrival() {
      for (let i = 0; i < 200 && arrivals.length === 0; i += 1) {
        await new Promise((r) => setTimeout(r, 5));
      }
      if (arrivals.length === 0) throw new Error('request never reached the boundary');
    },
    release,
  };
}

async function settle(promise: Promise<unknown>): Promise<unknown> {
  try {
    return await promise;
  } catch (err) {
    return err;
  }
}

function isRequestAborted(settlement: unknown): boolean {
  return settlement instanceof Error && settlement.name === 'RequestAbortedError';
}

describe('useQuerySubmit request lifetime (CHUNK-21 / IS-GAP-043)', () => {
  beforeEach(() => {
    resetSessionDeletionLifecycle();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('propagates an owned abort signal into the submit request', async () => {
    const pending = gatedEndpoint(['/api/v1/query/submit']);
    const { result, unmount } = renderHook(() => useQuerySubmit(), {
      wrapper: createWrapper(),
    });

    let flight: Promise<unknown> = Promise.resolve();
    act(() => {
      flight = settle(result.current.submitQuestion('q', null, 'connection-1'));
    });

    await pending.waitForArrival();
    expect(pending.signal?.aborted).toBe(false);

    unmount();
    expect(pending.signal?.aborted).toBe(true);
    pending.release();
    await act(async () => {
      await flight;
    });
  });

  it('suppresses frontend settlement after an intentional abort', async () => {
    const pending = gatedEndpoint(['/api/v1/query/submit']);
    const { result, unmount } = renderHook(() => useQuerySubmit(), {
      wrapper: createWrapper(),
    });

    let settlement: unknown;
    let flight: Promise<void> = Promise.resolve();
    act(() => {
      flight = settle(result.current.submitQuestion('q', null, 'connection-1')).then(
        (outcome) => {
          settlement = outcome;
        },
      );
    });

    await pending.waitForArrival();
    unmount();
    pending.release();
    await act(async () => {
      await flight;
    });

    expect(isRequestAborted(settlement)).toBe(true);
    expect(result.current.error).toBeNull();
    expect(result.current.result).toBeNull();
    expect(result.current.timeout).toBe(false);
    expect(result.current.evaluatorRejection).toBeNull();
    expect(result.current.refinePrompt).toBeNull();
  });

  it('aborts the in-flight request and suppresses settlement when CHUNK-03 deletion starts', async () => {
    const pending = gatedEndpoint(['/api/v1/query/submit']);
    const { result } = renderHook(() => useQuerySubmit(), {
      wrapper: createWrapper(),
    });

    let settlement: unknown;
    let flight: Promise<void> = Promise.resolve();
    act(() => {
      flight = settle(
        result.current.submitQuestion('q', 'session-1', 'connection-1'),
      ).then((outcome) => {
        settlement = outcome;
      });
    });

    await pending.waitForArrival();
    beginSessionDeletion('session-1');
    // Release the gate so the late response always arrives; it must never settle.
    pending.release();
    await act(async () => {
      await flight;
    });

    // The wire request is aborted and the late response is fully suppressed
    // while the frozen CHUNK-03 deletion contract keeps its error identity.
    expect(pending.signal?.aborted).toBe(true);
    expect(
      settlement instanceof Error &&
        ['RequestAbortedError', 'SessionDeletionError'].includes(settlement.name),
    ).toBe(true);
    expect(result.current.isSubmitting).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.result).toBeNull();
  });

  it('aborts the in-flight decision requests on unmount', async () => {
    const pending = gatedEndpoint([
      '/api/v1/query/reject',
      '/api/v1/query/regenerate',
      '/api/v1/query/accept',
    ]);
    const { result, unmount } = renderHook(() => useQuerySubmit(), {
      wrapper: createWrapper(),
    });

    let flights: Array<Promise<unknown>> = [];
    act(() => {
      flights = [
        settle(result.current.rejectQuery('attempt-1')),
        settle(result.current.regenerateQuery('attempt-1')),
        settle(result.current.acceptQuery('attempt-1', 'session-1')),
      ];
    });

    await pending.waitForArrival();
    // Decisions serialize through one in-flight guard; only the first request runs.
    expect(pending.signal).toBeDefined();
    unmount();
    pending.release();
    await act(async () => {
      await Promise.all(flights);
    });

    expect(pending.signal?.aborted).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it('keeps backend timeout classification distinct from any client deadline', async () => {
    server.use(
      http.post(
        '/api/v1/query/submit',
        () =>
          HttpResponse.json(
            { error: 'timeout', message_key: 'error.timeout' },
            { status: 504 },
          ),
        { once: true },
      ),
    );
    const { result } = renderHook(() => useQuerySubmit(), { wrapper: createWrapper() });
    await act(async () => {
      await settle(result.current.submitQuestion('q', null, 'connection-1'));
    });
    expect(result.current.timeout).toBe(true);
    expect(result.current.error).toBeNull();
  });
});

import React from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { InfiniteData, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { useSessionsList, useSessionDetail, useCreateSession, useDeleteSession } from '../useSessions';
import { useUpdateFeedback } from '../useFeedback';
import { useAdminSettings, useUpdateAdminSettings } from '../useAdminSettings';
import { createWrapper, seedAuthenticatedUser } from '../../test/utils';
import { server } from '../../test/server';
import {
  isSessionUnavailable,
  resetSessionDeletionLifecycle,
} from '../../sessionDeletionLifecycle';

const SESSION_ID = '550e8400-e29b-41d4-a716-446655440001';

interface PaginatedHookResult {
  fetchNextPage: () => Promise<unknown>;
  hasNextPage: boolean;
}

function deleteHookWrapper(queryClient: QueryClient) {
  seedAuthenticatedUser(queryClient);
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useSessions hooks', () => {
  beforeEach(() => {
    resetSessionDeletionLifecycle();
  });
  it('useSessionsList returns data shape', async () => {
    const { result } = renderHook(() => useSessionsList(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    if (result.current.error) {
      console.log('Query error:', result.current.error);
    }
    // With MSW, this should return mock data or error gracefully
    expect(result.current.data).toBeDefined();
  });


  it('useSessionDetail is disabled when sessionId is empty', () => {
    const { result } = renderHook(() => useSessionDetail(''), { wrapper: createWrapper() });
    expect(result.current.isLoading).toBe(false);
    expect(result.current.fetchStatus).toBe('idle');
  });

  it('loads and deduplicates session pages only after explicit pagination', async () => {
    const requestedCursors: Array<string | null> = [];
    server.use(
      http.get('/api/v1/sessions', ({ request }) => {
        const cursor = new URL(request.url).searchParams.get('cursor');
        requestedCursors.push(cursor);
        if (cursor === 'sessions-page-2') {
          return HttpResponse.json({
            items: [
              { id: 'session-1', preview_text: 'duplicate', created_at: '2026-08-12T00:00:00Z', last_activity_at: '2026-08-12T00:00:00Z' },
              { id: 'session-2', preview_text: 'second', created_at: '2026-08-11T00:00:00Z', last_activity_at: '2026-08-11T00:00:00Z' },
            ],
            total: 2,
            next_cursor: null,
          });
        }
        return HttpResponse.json({
          items: [
            { id: 'session-1', preview_text: 'first', created_at: '2026-08-12T00:00:00Z', last_activity_at: '2026-08-12T00:00:00Z' },
          ],
          total: 2,
          next_cursor: 'sessions-page-2',
        });
      })
    );

    const { result } = renderHook(() => useSessionsList(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.data?.items).toHaveLength(1));
    expect(requestedCursors).toEqual([null]);

    const pagination = result.current as typeof result.current & PaginatedHookResult;
    expect(pagination.hasNextPage).toBe(true);
    await act(async () => {
      await pagination.fetchNextPage();
    });

    await waitFor(() => expect(result.current.data?.items.map((session) => session.id)).toEqual(['session-1', 'session-2']));
    expect(requestedCursors).toEqual([null, 'sessions-page-2']);
  });

  it('paginates and deduplicates session attempts', async () => {
    const requestedCursors: Array<string | null> = [];
    server.use(
      http.get('/api/v1/sessions/:sessionId', ({ params, request }) => {
        const cursor = new URL(request.url).searchParams.get('attempt_cursor');
        requestedCursors.push(cursor);
        const base = {
          id: params.sessionId as string,
          connection_id: null,
          preview_text: '',
          created_at: '2026-08-10T00:00:00Z',
          last_activity_at: '2026-08-12T00:00:00Z',
          attempts_total: 3,
        };
        if (cursor === 'attempt-page-2') {
          return HttpResponse.json({
            ...base,
            attempts: [
              { id: 'attempt-2', question_text: '', generated_sql: '', accepted_at: '2026-08-11T00:00:00Z', saved: true },
              { id: 'attempt-1', question_text: '', generated_sql: '', accepted_at: '2026-08-10T00:00:00Z', saved: true },
            ],
            attempts_next_cursor: null,
          });
        }
        return HttpResponse.json({
          ...base,
          attempts: [
            { id: 'attempt-3', question_text: '', generated_sql: '', accepted_at: '2026-08-12T00:00:00Z', saved: true },
            { id: 'attempt-2', question_text: '', generated_sql: '', accepted_at: '2026-08-11T00:00:00Z', saved: true },
          ],
          attempts_next_cursor: 'attempt-page-2',
        });
      })
    );

    const { result } = renderHook(() => useSessionDetail(SESSION_ID), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.data?.attempts).toHaveLength(2));
    expect(requestedCursors).toEqual([null]);

    const pagination = result.current as typeof result.current & PaginatedHookResult;
    await act(async () => {
      await pagination.fetchNextPage();
    });

    await waitFor(() => expect(result.current.data?.attempts.map((attempt) => attempt.id)).toEqual([
      'attempt-3',
      'attempt-2',
      'attempt-1',
    ]));
    expect(requestedCursors).toEqual([null, 'attempt-page-2']);
  });

  it('aborts the old detail page and suppresses late settlement after a session switch', async () => {
    let releaseOldPage: (() => void) | undefined;
    let oldRequestAborted = false;
    server.use(
      http.get('/api/v1/sessions/:sessionId', async ({ params, request }) => {
        if (params.sessionId === 'old-session') {
          await new Promise<void>((resolve) => {
            releaseOldPage = resolve;
            request.signal.addEventListener('abort', () => {
              oldRequestAborted = true;
              resolve();
            }, { once: true });
          });
        }
        return HttpResponse.json({
          id: params.sessionId as string,
          connection_id: null,
          preview_text: '',
          created_at: '2026-08-10T00:00:00Z',
          last_activity_at: '2026-08-12T00:00:00Z',
          attempts: [],
          attempts_total: 0,
          attempts_next_cursor: null,
        });
      })
    );

    const { result, rerender } = renderHook(
      ({ sessionId }) => useSessionDetail(sessionId),
      { initialProps: { sessionId: 'old-session' }, wrapper: createWrapper() }
    );
    await waitFor(() => expect(releaseOldPage).toBeDefined());
    rerender({ sessionId: 'new-session' });
    await waitFor(() => expect(result.current.data?.id).toBe('new-session'));

    expect(oldRequestAborted).toBe(true);
    releaseOldPage?.();
    await Promise.resolve();
    expect(result.current.data?.id).toBe('new-session');
  });

  it('useCreateSession returns mutation function', () => {
    const { result } = renderHook(() => useCreateSession(), { wrapper: createWrapper() });
    expect(typeof result.current.mutate).toBe('function');
  });

  it('useDeleteSession returns mutation function', () => {
    const { result } = renderHook(() => useDeleteSession(), { wrapper: createWrapper() });
    expect(typeof result.current.mutate).toBe('function');
  });

  it('removes deleted session detail/list cache and keeps the lifecycle invalidated', async () => {
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    queryClient.setQueryData(['sessions'], {
      pages: [
        { items: [{ id: 'other-session' }], total: 2, next_cursor: 'page-2' },
        { items: [{ id: SESSION_ID }], total: 2, next_cursor: null },
      ],
      pageParams: [undefined, 'page-2'],
    } satisfies InfiniteData<unknown>);
    queryClient.setQueryData(['sessions', SESSION_ID], {
      pages: [{ id: SESSION_ID, attempts: [], attempts_total: 0, attempts_next_cursor: null }],
      pageParams: [undefined],
    } satisfies InfiniteData<unknown>);
    const { result } = renderHook(() => useDeleteSession(), {
      wrapper: deleteHookWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync(SESSION_ID);
    });

    expect(queryClient.getQueryData(['sessions', SESSION_ID])).toBeUndefined();
    const cachedPages = queryClient.getQueryData<InfiniteData<{ items: Array<{ id: string }>; total: number }>>(['sessions']);
    expect(cachedPages?.pages.map((page) => page.items)).toEqual([[{ id: 'other-session' }], []]);
    expect(cachedPages?.pages.map((page) => page.total)).toEqual([1, 1]);
    expect(isSessionUnavailable(SESSION_ID)).toBe(true);
  });

  it('restores session detail and lifecycle state when DELETE fails', async () => {
    server.use(
      http.delete('/api/v1/sessions/:sessionId', () =>
        HttpResponse.json(
          { error: 'service_unavailable', message_key: 'error.service_unavailable' },
          { status: 503 }
        )
      )
    );
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const detail = {
      pages: [{ id: SESSION_ID, attempts: [], attempts_total: 0, attempts_next_cursor: null }],
      pageParams: [undefined],
    };
    queryClient.setQueryData(['sessions'], {
      pages: [{ items: [{ id: SESSION_ID }], total: 1, next_cursor: null }],
      pageParams: [undefined],
    });
    queryClient.setQueryData(['sessions', SESSION_ID], detail);
    const { result } = renderHook(() => useDeleteSession(), {
      wrapper: deleteHookWrapper(queryClient),
    });

    await expect(
      act(async () => {
        await result.current.mutateAsync(SESSION_ID);
      })
    ).rejects.toBeDefined();

    expect(queryClient.getQueryData(['sessions', SESSION_ID])).toEqual(detail);
    expect(isSessionUnavailable(SESSION_ID)).toBe(false);
    expect(queryClient.getQueryState(['sessions'])?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(['sessions', SESSION_ID])?.isInvalidated).toBe(true);
  });
});

describe('useFeedback hook', () => {
  it('useUpdateFeedback returns mutation function', () => {
    const { result } = renderHook(() => useUpdateFeedback(), { wrapper: createWrapper() });
    expect(typeof result.current.mutate).toBe('function');
  });
});

describe('useAdminSettings hooks', () => {
  it('useAdminSettings returns data shape', async () => {
    const { result } = renderHook(() => useAdminSettings(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.data).toBeDefined();
  });

  it('useUpdateAdminSettings returns mutation function', () => {
    const { result } = renderHook(() => useUpdateAdminSettings(), { wrapper: createWrapper() });
    expect(typeof result.current.mutate).toBe('function');
  });
});

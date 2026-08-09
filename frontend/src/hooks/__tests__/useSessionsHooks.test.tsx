import React from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
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
    queryClient.setQueryData(['sessions'], { items: [{ id: SESSION_ID }], total: 1 });
    queryClient.setQueryData(['sessions', SESSION_ID], { id: SESSION_ID, attempts: [] });
    const { result } = renderHook(() => useDeleteSession(), {
      wrapper: deleteHookWrapper(queryClient),
    });

    await result.current.mutateAsync(SESSION_ID);

    expect(queryClient.getQueryData(['sessions', SESSION_ID])).toBeUndefined();
    expect(queryClient.getQueryData<{ items: unknown[]; total: number }>(['sessions'])).toEqual({
      items: [],
      total: 0,
    });
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
    const detail = { id: SESSION_ID, attempts: [] };
    queryClient.setQueryData(['sessions'], { items: [{ id: SESSION_ID }], total: 1 });
    queryClient.setQueryData(['sessions', SESSION_ID], detail);
    const { result } = renderHook(() => useDeleteSession(), {
      wrapper: deleteHookWrapper(queryClient),
    });

    await expect(result.current.mutateAsync(SESSION_ID)).rejects.toBeDefined();

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

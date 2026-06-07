import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useSessionsList, useSessionDetail, useCreateSession, useDeleteSession } from '../useSessions';
import { useUpdateFeedback } from '../useFeedback';
import { useAdminSettings, useUpdateAdminSettings } from '../useAdminSettings';
import { createWrapper } from '../../test/utils';

describe('useSessions hooks', () => {
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

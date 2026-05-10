import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useHistory } from '../useHistory';

vi.mock('../../api/historyApi', () => ({
  listHistory: vi.fn(),
  getHistoryItem: vi.fn(),
}));

import * as historyApi from '../../api/historyApi';

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('useHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches history list on mount and exposes data + isLoading', async () => {
    vi.mocked(historyApi.listHistory).mockResolvedValueOnce({
      items: [{ id: '1', question_text: 'Q1', generated_sql: 'SELECT 1', accepted_at: '2026-05-11T00:00:00Z' }],
      total: 1,
      next_cursor: null,
    });
    const { result } = renderHook(() => useHistory(), { wrapper });
    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.items).toHaveLength(1);
    expect(result.current.total).toBe(1);
  });

  it('supports pagination via fetchNextPage and exposes hasNextPage', async () => {
    vi.mocked(historyApi.listHistory)
      .mockResolvedValueOnce({ items: [{ id: '1' }], total: 2, next_cursor: 'c2' })
      .mockResolvedValueOnce({ items: [{ id: '2' }], total: 2, next_cursor: null });
    const { result } = renderHook(() => useHistory(), { wrapper });
    await waitFor(() => expect(result.current.hasNextPage).toBe(true));
    await act(async () => { await result.current.fetchNextPage(); });
    expect(result.current.items).toHaveLength(2);
    expect(result.current.hasNextPage).toBe(false);
  });

  it('exposes error state when fetch fails', async () => {
    vi.mocked(historyApi.listHistory).mockRejectedValueOnce(new Error('network'));
    const { result } = renderHook(() => useHistory(), { wrapper });
    await waitFor(() => expect(result.current.error).toBeTruthy());
  });
});

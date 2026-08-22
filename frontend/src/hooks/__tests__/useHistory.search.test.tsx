import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useHistory } from '../useHistory';
import { seedAuthenticatedUser } from '../../test/utils';

vi.mock('../../api/historyApi', () => ({
  listHistory: vi.fn(),
  getHistoryItem: vi.fn(),
}));

import * as historyApi from '../../api/historyApi';

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  seedAuthenticatedUser(qc);
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('useHistory server-side search (IS-GAP-032)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sends the normalized search term to the server', async () => {
    vi.mocked(historyApi.listHistory).mockResolvedValue({
      items: [{ id: '2', question_text: 'Revenue top', generated_sql: 'SELECT 2', accepted_at: '2026-05-11T00:00:00Z' }],
      total: 1,
      next_cursor: null,
    });
    const { result } = renderHook(() => useHistory({ search: '  revenue  ' }), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(historyApi.listHistory).toHaveBeenCalledWith(
      expect.objectContaining({ search: 'revenue' }),
      expect.anything()
    );
    expect(result.current.items).toHaveLength(1);
  });

  it('omits the search parameter for blank/whitespace searches', async () => {
    vi.mocked(historyApi.listHistory).mockResolvedValue({ items: [], total: 0, next_cursor: null });
    const { result } = renderHook(() => useHistory({ search: '   ' }), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(historyApi.listHistory).toHaveBeenCalledWith(
      expect.objectContaining({ search: undefined }),
      expect.anything()
    );
  });

  it('keeps results for different search terms in separate cache entries', async () => {
    vi.mocked(historyApi.listHistory).mockImplementation(async (params?) => ({
      items: [
        {
          id: params?.search === 'revenue' ? 'rev-1' : 'all-1',
          question_text: params?.search ?? 'all',
          generated_sql: 'SELECT 1',
          accepted_at: '2026-05-11T00:00:00Z',
        },
      ],
      total: 1,
      next_cursor: null,
    }));

    const { result, rerender } = renderHook(
      ({ search }: { search?: string }) => useHistory({ search }),
      { wrapper, initialProps: { search: 'revenue' as string | undefined } }
    );
    await waitFor(() => expect(result.current.items[0]?.id).toBe('rev-1'));

    rerender({ search: undefined });
    await waitFor(() => expect(result.current.items[0]?.id).toBe('all-1'));

    // Returning to the earlier search restores its own cached result set.
    rerender({ search: 'revenue' });
    await waitFor(() => expect(result.current.items[0]?.id).toBe('rev-1'));
  });

  it('does not let a stale unfiltered response override an active search', async () => {
    let resolveAll: (value: unknown) => void = () => {};
    vi.mocked(historyApi.listHistory).mockImplementation(async (params?) => {
      if (!params?.search) {
        await new Promise((resolve) => {
          resolveAll = resolve;
        });
        return { items: [{ id: 'stale', question_text: 'stale', generated_sql: '', accepted_at: '' }], total: 99, next_cursor: null };
      }
      return { items: [{ id: 'filtered', question_text: 'filtered', generated_sql: '', accepted_at: '' }], total: 1, next_cursor: null };
    });

    const { result, rerender } = renderHook(
      ({ search }: { search?: string }) => useHistory({ search }),
      { wrapper, initialProps: { search: undefined as string | undefined } }
    );
    await waitFor(() => expect(historyApi.listHistory).toHaveBeenCalledTimes(1));

    rerender({ search: 'needle' });
    await waitFor(() =>
      expect(result.current.items.map((item) => item.id)).toEqual(['filtered'])
    );

    // The slow unfiltered response settles late — it must not leak into the
    // active filtered view.
    await act(async () => {
      resolveAll(undefined);
      await Promise.resolve();
    });
    await waitFor(() => {
      expect(result.current.items.map((item) => item.id)).toEqual(['filtered']);
    });
  });

  it('exposes the filtered first-page total', async () => {
    vi.mocked(historyApi.listHistory).mockResolvedValue({ items: [], total: 7, next_cursor: 'c2' });
    const { result } = renderHook(() => useHistory({ search: 'needle' }), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.total).toBe(7);
    expect(result.current.hasNextPage).toBe(true);
  });
});

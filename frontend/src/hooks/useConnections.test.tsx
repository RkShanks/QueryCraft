import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useConnections } from './useConnections';
import { listAdminConnections } from '../api/generated/sdk.gen';

vi.mock('../api/generated/sdk.gen', () => ({
  listAdminConnections: vi.fn(),
  createAdminConnection: vi.fn(),
  updateAdminConnection: vi.fn(),
  deleteAdminConnection: vi.fn(),
  testAdminConnection: vi.fn(),
  disableAdminConnection: vi.fn(),
  enableAdminConnection: vi.fn(),
  refreshSchema: vi.fn(),
}));

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={queryClient}>
    {children}
  </QueryClientProvider>
);

describe('useConnections', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryClient.clear();
  });

  it('handles loading and successful list fetch', async () => {
    const mockConnections = {
      connections: [
        { id: '1', display_name: 'Test DB', database_type: 'postgresql', lifecycle_state: 'active' },
      ],
    };
    
    vi.mocked(listAdminConnections).mockResolvedValueOnce({
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      data: mockConnections as any,
      response: new Response(),
      request: new Request('http://localhost'),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    const { result } = renderHook(() => useConnections(), { wrapper });

    expect(result.current.listQuery.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.listQuery.isSuccess).toBe(true);
    });

    expect(result.current.listQuery.data).toEqual(mockConnections);
  });

  it('handles empty state data', async () => {
    vi.mocked(listAdminConnections).mockResolvedValueOnce({
      data: { connections: [] },
      response: new Response(),
      request: new Request('http://localhost'),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    const { result } = renderHook(() => useConnections(), { wrapper });

    await waitFor(() => {
      expect(result.current.listQuery.isSuccess).toBe(true);
    });

    expect(result.current.listQuery.data?.connections).toHaveLength(0);
  });

  it('handles error path', async () => {
    vi.mocked(listAdminConnections).mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useConnections(), { wrapper });

    await waitFor(() => {
      expect(result.current.listQuery.isError).toBe(true);
    });

    expect(result.current.listQuery.error).toBeDefined();
  });
});

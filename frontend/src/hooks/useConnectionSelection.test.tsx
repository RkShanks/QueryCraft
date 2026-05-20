import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useConnectionSelection } from './useConnectionSelection';
import { updateSessionConnection } from '../api/generated/sdk.gen';
import type { UserConnectionResponse } from '../api/generated/types.gen';

vi.mock('../api/generated/sdk.gen', () => ({
  updateSessionConnection: vi.fn(),
}));

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={queryClient}>
    {children}
  </QueryClientProvider>
);

const makeConnection = (id: string, display_name: string, database_type: 'postgresql' | 'mysql' | 'mssql' = 'postgresql'): UserConnectionResponse => ({
  id,
  display_name,
  database_type,
});

describe('useConnectionSelection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryClient.clear();
  });

  it('initializes with existing selected connection id', () => {
    const { result } = renderHook(
      () => useConnectionSelection({
        sessionId: 'session-1',
        initialConnectionId: 'conn-a',
        availableConnections: [makeConnection('conn-a', 'DB A')],
      }),
      { wrapper }
    );

    expect(result.current.selectedConnectionId).toBe('conn-a');
  });

  it('auto-selects single available connection when no initial selection', async () => {
    const { result } = renderHook(
      () => useConnectionSelection({
        sessionId: 'session-1',
        initialConnectionId: null,
        availableConnections: [makeConnection('conn-a', 'DB A')],
      }),
      { wrapper }
    );

    await waitFor(() => {
      expect(result.current.selectedConnectionId).toBe('conn-a');
    });
  });

  it('does not auto-select when multiple connections exist', () => {
    const { result } = renderHook(
      () => useConnectionSelection({
        sessionId: 'session-1',
        initialConnectionId: null,
        availableConnections: [
          makeConnection('conn-a', 'DB A'),
          makeConnection('conn-b', 'DB B'),
        ],
      }),
      { wrapper }
    );

    expect(result.current.selectedConnectionId).toBeNull();
  });

  it('calls session connection PATCH on user selection', async () => {
    vi.mocked(updateSessionConnection).mockResolvedValueOnce({
      data: { id: 'session-1', preview_text: 'Test', created_at: new Date().toISOString(), last_activity_at: new Date().toISOString(), attempts: [] },
      response: new Response(),
      request: new Request('http://localhost'),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    const { result } = renderHook(
      () => useConnectionSelection({
        sessionId: 'session-1',
        initialConnectionId: null,
        availableConnections: [makeConnection('conn-a', 'DB A')],
      }),
      { wrapper }
    );

    act(() => {
      result.current.setSelectedConnectionId('conn-a');
    });

    await waitFor(() => {
      expect(updateSessionConnection).toHaveBeenCalledTimes(1);
    });

    expect(updateSessionConnection).toHaveBeenCalledWith(
      expect.objectContaining({
        path: { sessionId: 'session-1' },
        body: { connection_id: 'conn-a' },
      })
    );
  });

  it('does not PATCH when no session id is available', async () => {
    const { result } = renderHook(
      () => useConnectionSelection({
        sessionId: null,
        initialConnectionId: null,
        availableConnections: [makeConnection('conn-a', 'DB A')],
      }),
      { wrapper }
    );

    act(() => {
      result.current.setSelectedConnectionId('conn-a');
    });

    // Allow any async effects to settle
    await new Promise((r) => setTimeout(r, 50));

    expect(updateSessionConnection).not.toHaveBeenCalled();
  });

  it('does not duplicate PATCH for same connection id', async () => {
    vi.mocked(updateSessionConnection).mockResolvedValueOnce({
      data: { id: 'session-1', preview_text: 'Test', created_at: new Date().toISOString(), last_activity_at: new Date().toISOString(), attempts: [] },
      response: new Response(),
      request: new Request('http://localhost'),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    const { result } = renderHook(
      () => useConnectionSelection({
        sessionId: 'session-1',
        initialConnectionId: null,
        availableConnections: [makeConnection('conn-a', 'DB A')],
      }),
      { wrapper }
    );

    act(() => {
      result.current.setSelectedConnectionId('conn-a');
    });

    await waitFor(() => {
      expect(updateSessionConnection).toHaveBeenCalledTimes(1);
    });

    // Select same again
    act(() => {
      result.current.setSelectedConnectionId('conn-a');
    });

    await new Promise((r) => setTimeout(r, 50));

    expect(updateSessionConnection).toHaveBeenCalledTimes(1);
  });

  it('exposes mutation error state', async () => {
    vi.mocked(updateSessionConnection).mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(
      () => useConnectionSelection({
        sessionId: 'session-1',
        initialConnectionId: null,
        availableConnections: [makeConnection('conn-a', 'DB A')],
      }),
      { wrapper }
    );

    act(() => {
      result.current.setSelectedConnectionId('conn-a');
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeDefined();
  });

  it('keeps prior selected value stable if available connections refetch without changing selected id', () => {
    const { result, rerender } = renderHook(
      ({ connections }) => useConnectionSelection({
        sessionId: 'session-1',
        initialConnectionId: 'conn-a',
        availableConnections: connections,
      }),
      {
        wrapper,
        initialProps: {
          connections: [makeConnection('conn-a', 'DB A')],
        },
      }
    );

    expect(result.current.selectedConnectionId).toBe('conn-a');

    rerender({
      connections: [makeConnection('conn-a', 'DB A'), makeConnection('conn-b', 'DB B')],
    });

    expect(result.current.selectedConnectionId).toBe('conn-a');
  });

  it('handles no-connections state without calling PATCH', async () => {
    const { result } = renderHook(
      () => useConnectionSelection({
        sessionId: 'session-1',
        initialConnectionId: null,
        availableConnections: [],
      }),
      { wrapper }
    );

    expect(result.current.selectedConnectionId).toBeNull();
    expect(updateSessionConnection).not.toHaveBeenCalled();
  });
});

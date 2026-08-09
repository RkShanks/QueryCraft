import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useConnections } from './useConnections';
import {
  createAdminConnection,
  disableAdminConnection,
  enableAdminConnection,
  listAdminConnections,
  updateAdminConnection,
} from '../api/generated/sdk.gen';
import { seedAuthenticatedUser } from '../test/utils';

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

const legacyConnectionWithSensitiveExtras = (runtimeProbes: string[]) => ({
  id: '1',
  display_name: 'Test DB',
  database_type: 'postgresql',
  host: runtimeProbes[0],
  port: 5432,
  database_name: 'app',
  username: runtimeProbes[1],
  ssl_mode: 'require',
  lifecycle_state: 'active',
  health_status: 'healthy',
  last_health_check_at: null,
  health_error_category: null,
  schema_introspection_status: 'success',
  schema_last_refreshed_at: null,
  created_at: '2026-07-29T00:00:00Z',
  updated_at: '2026-07-29T00:00:00Z',
  password: runtimeProbes[2],
  encrypted_password: runtimeProbes[3],
  database_url: runtimeProbes[4],
  Host: runtimeProbes[5],
  USERNAME: runtimeProbes[5],
  metadata: { label: runtimeProbes[6] },
  display_hint: btoa(runtimeProbes[7]),
});

describe('useConnections', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryClient.clear();
    seedAuthenticatedUser(queryClient);
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

  it.each([
    ['a raw array', (connection: Record<string, unknown>) => [connection]],
    ['a wrapped object', (connection: Record<string, unknown>) => ({ connections: [connection] })],
  ])('normalizes %s response into a cache-safe connection list', async (_name, responseShape) => {
    const runtimeProbes = Array.from({ length: 8 }, () => crypto.randomUUID());
    const legacyConnection = legacyConnectionWithSensitiveExtras(runtimeProbes);
    vi.mocked(listAdminConnections).mockResolvedValueOnce({
      data: responseShape(legacyConnection),
      response: new Response(),
      request: new Request('http://localhost'),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    const { result } = renderHook(() => useConnections(), { wrapper });

    await waitFor(() => expect(result.current.listQuery.isFetching).toBe(false));

    expect(result.current.listQuery.isSuccess).toBe(true);
    const normalizedConnection = result.current.listQuery.data?.connections[0];
    const serializedConnection = JSON.stringify(normalizedConnection);
    expect(normalizedConnection).toBeDefined();
    expect(runtimeProbes.every((probe) => !serializedConnection.includes(probe))).toBe(true);
  });

  it('keeps legacy write-only and unexpected response fields out of the query cache', async () => {
    const runtimeProbes = Array.from({ length: 8 }, () => crypto.randomUUID());
    vi.mocked(listAdminConnections).mockResolvedValueOnce({
      data: {
        connections: [legacyConnectionWithSensitiveExtras(runtimeProbes)],
      },
      response: new Response(),
      request: new Request('http://localhost'),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    renderHook(() => useConnections(), { wrapper });

    await waitFor(() => {
      expect(queryClient.getQueryState(['adminConnections'])?.status).toBe('success');
    });

    const cachedList = queryClient.getQueryData<{
      connections: Array<Record<string, unknown>>;
    }>(['adminConnections']);
    const cachedConnection = cachedList?.connections[0];
    const serializedConnection = JSON.stringify(cachedConnection);

    expect(cachedConnection).toBeDefined();
    expect(runtimeProbes.every((probe) => !serializedConnection.includes(probe))).toBe(true);
    expect(Object.keys(cachedConnection ?? {}).sort()).toEqual(
      [
        'created_at',
        'database_name',
        'database_type',
        'display_name',
        'health_error_category',
        'health_status',
        'id',
        'last_health_check_at',
        'lifecycle_state',
        'port',
        'schema_introspection_status',
        'schema_last_refreshed_at',
        'ssl_mode',
        'updated_at',
      ].sort()
    );
    expect(vi.mocked(listAdminConnections).mock.calls[0]?.[0]?.cache).toBe('no-store');
  });

  it('keeps write-only and unexpected fields out of connection mutation results', async () => {
    const runtimeProbes = Array.from({ length: 8 }, () => crypto.randomUUID());
    const legacyConnectionResponse = legacyConnectionWithSensitiveExtras(runtimeProbes);
    const sdkResponse = {
      data: legacyConnectionResponse,
      response: new Response(),
      request: new Request('http://localhost'),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any;
    vi.mocked(listAdminConnections).mockResolvedValue({
      data: { connections: [] },
      response: new Response(),
      request: new Request('http://localhost'),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);
    vi.mocked(createAdminConnection).mockResolvedValueOnce(sdkResponse);
    vi.mocked(updateAdminConnection).mockResolvedValueOnce(sdkResponse);
    vi.mocked(disableAdminConnection).mockResolvedValueOnce(sdkResponse);
    vi.mocked(enableAdminConnection).mockResolvedValueOnce(sdkResponse);

    const { result } = renderHook(() => useConnections(), { wrapper });
    await waitFor(() => expect(result.current.listQuery.isSuccess).toBe(true));

    let mutationResults: Array<Record<string, unknown>> = [];
    await act(async () => {
      mutationResults = [
        await result.current.createMutation.mutateAsync({
          display_name: 'Test DB',
          database_type: 'postgresql',
          host: crypto.randomUUID(),
          port: 5432,
          database_name: 'app',
          username: crypto.randomUUID(),
          password: crypto.randomUUID(),
        }),
        await result.current.updateMutation.mutateAsync({ id: '1', data: {} }),
        await result.current.disableMutation.mutateAsync('1'),
        await result.current.enableMutation.mutateAsync('1'),
      ];
    });

    const serializedResults = JSON.stringify(mutationResults);
    expect(runtimeProbes.every((probe) => !serializedResults.includes(probe))).toBe(true);
    expect(
      mutationResults.every(
        (connection) =>
          !Object.hasOwn(connection, 'host') &&
          !Object.hasOwn(connection, 'username') &&
          !Object.hasOwn(connection, 'password') &&
          !Object.hasOwn(connection, 'encrypted_password') &&
          !Object.hasOwn(connection, 'database_url') &&
          !Object.hasOwn(connection, 'metadata')
      )
    ).toBe(true);
    expect(vi.mocked(createAdminConnection).mock.calls[0]?.[0]?.cache).toBe('no-store');
    expect(vi.mocked(updateAdminConnection).mock.calls[0]?.[0]?.cache).toBe('no-store');
    expect(vi.mocked(disableAdminConnection).mock.calls[0]?.[0]?.cache).toBe('no-store');
    expect(vi.mocked(enableAdminConnection).mock.calls[0]?.[0]?.cache).toBe('no-store');
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

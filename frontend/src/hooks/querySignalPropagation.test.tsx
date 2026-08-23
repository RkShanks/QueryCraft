import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useCurrentUser, useSsoProviders } from './useAuth';
import { useConnectionSchema } from './useConnectionSchema';
import { useAdminSettings } from './useAdminSettings';
import { server } from '../test/server';
import { http, HttpResponse } from 'msw';
import { seedAuthenticatedUser } from '../test/utils';

/**
 * CHUNK-21 / IS-GAP-043 — every consumed query function must propagate the
 * TanStack-supplied signal so cancelled/unmounted queries abort on the wire.
 * The observable proof: cancelling the query aborts the in-flight request.
 */
describe('query signal propagation through consumed clients', () => {
  const captured: AbortSignal[] = [];

  function harness() {
    captured.length = 0;
    server.use(
      http.get('/api/v1/auth/me', async ({ request }) => {
        captured.push(request.signal);
        await new Promise((r) => setTimeout(r, 250));
        return HttpResponse.json({
          id: 'u1',
          username: 'user',
          display_name: 'User',
          role: 'admin',
          permissions: [],
          auth_provider: 'local',
        });
      }),
      http.get('/api/v1/auth/sso/providers', async ({ request }) => {
        captured.push(request.signal);
        await new Promise((r) => setTimeout(r, 250));
        return HttpResponse.json({ providers: [] });
      }),
      http.get('/api/v1/admin/settings', async ({ request }) => {
        captured.push(request.signal);
        await new Promise((r) => setTimeout(r, 250));
        return HttpResponse.json({ max_question_length: 2000 });
      }),
      http.get('/api/v1/admin/connections/c1/schema', async ({ request }) => {
        captured.push(request.signal);
        await new Promise((r) => setTimeout(r, 250));
        return HttpResponse.json({ tables: [] });
      }),
    );
  }

  afterEach(() => {
    captured.length = 0;
  });

  function permissionedClient() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    seedAuthenticatedUser(client);
    return client;
  }

  async function renderAndCancel(
    useHook: () => unknown,
    buildClient: () => QueryClient = () =>
      new QueryClient({ defaultOptions: { queries: { retry: false } } }),
  ) {
    const client = buildClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const { unmount } = renderHook(() => useHook(), { wrapper });
    for (let i = 0; i < 100 && captured.length === 0; i += 1) {
      await new Promise((r) => setTimeout(r, 5));
    }
    expect(captured.length).toBeGreaterThan(0);
    await act(async () => {
      await client.cancelQueries();
    });
    unmount();
    return waitFor(() => expect(captured[0].aborted).toBe(true));
  }

  it('propagates the signal through the fallback current-user query', async () => {
    harness();
    await renderAndCancel(() => useCurrentUser());
  });

  it('propagates the signal through the SSO provider discovery query', async () => {
    harness();
    await renderAndCancel(() => useSsoProviders());
  });

  it('propagates the signal through the admin settings query', async () => {
    harness();
    await renderAndCancel(() => useAdminSettings(), permissionedClient);
  });

  it('propagates the signal through the connection schema query', async () => {
    harness();
    await renderAndCancel(() => useConnectionSchema('c1'), permissionedClient);
  });

  it('keeps ordinary reads cancellable without a hard-coded query deadline', async () => {
    harness();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const { unmount } = renderHook(() => useSsoProviders(), { wrapper });
    for (let i = 0; i < 100 && captured.length === 0; i += 1) {
      await new Promise((r) => setTimeout(r, 5));
    }
    // No deadline is attached by the caller: only an explicit cancel aborts it.
    await new Promise((r) => setTimeout(r, 60));
    expect(captured[0].aborted).toBe(false);
    unmount();
  });
});

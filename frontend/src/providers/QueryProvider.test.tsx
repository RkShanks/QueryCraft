/* eslint-disable local/no-inline-user-strings */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useLayoutEffect } from 'react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { CURRENT_USER_QUERY_KEY, QueryProvider, queryClient } from './QueryProvider';
import { useCurrentUser, useSignIn, useSignOut } from '../hooks/useAuth';
import { useUIStore } from '../stores/uiStore';
import { http, HttpResponse } from 'msw';
import { server } from '../test/server';
import { client as apiClient } from '../api/generated/client.gen';

function ExpiredSessionProbe() {
  const query = useQuery({
    queryKey: ['expired-session-probe'],
    queryFn: async () => {
      throw {
        error: 'unauthorized',
        message_key: 'error.unauthorized',
      };
    },
    retry: false,
  });
  return query.isError ? <span data-testid="query-rejected" /> : null;
}

function deferredValue<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

function IdentityBoundaryProbe() {
  const currentUser = useCurrentUser();
  const featureClient = useQueryClient();
  const activeSessionId = useUIStore((state) => state.activeSessionId);
  const hoveredSessionId = useUIStore((state) => state.hoveredSessionId);
  const promptDraft = useUIStore((state) => state.promptDraft);
  const sidebarCollapsed = useUIStore((state) => state.sidebarCollapsed);
  const history = useQuery({
    queryKey: ['identity-boundary-history'],
    queryFn: async () => {
      const response = await fetch('/api/v1/identity-boundary-history');
      return (await response.json()) as { owner: string };
    },
    retry: false,
  });

  return (
    <div>
      <span data-testid="identity">{currentUser.data?.data?.id}</span>
      <span data-testid="history-owner">{history.data?.owner}</span>
      <span data-testid="active-session">{activeSessionId ?? 'none'}</span>
      <span data-testid="hovered-session">{hoveredSessionId ?? 'none'}</span>
      <span data-testid="prompt-draft">{promptDraft}</span>
      <span data-testid="sidebar-collapsed">{String(sidebarCollapsed)}</span>
      <span data-testid="feature-cache-owner">
        {featureClient.getQueryData<{ owner: string }>(['identity-boundary-history'])?.owner}
      </span>
      <button type="button" onClick={() => currentUser.refetch()}>
        Refresh identity
      </button>
    </div>
  );
}

function MutationBoundaryProbe() {
  const currentUser = useCurrentUser();
  const featureClient = useQueryClient();
  const featureState = useQuery({
    queryKey: ['mutation-boundary-state'],
    queryFn: async () => {
      const response = await fetch('/api/v1/mutation-boundary-state');
      return (await response.json()) as { owner: string };
    },
    retry: false,
  });
  const mutation = useMutation({
    mutationFn: async () => {
      const response = await fetch('/api/v1/late-user-a-mutation', { method: 'POST' });
      return response.json();
    },
    onSuccess: () => {
      void featureClient.invalidateQueries({ queryKey: ['mutation-boundary-state'] });
    },
  });

  return (
    <div>
      <span data-testid="mutation-identity">{currentUser.data?.data?.id}</span>
      <span data-testid="mutation-state-owner">{featureState.data?.owner}</span>
      <button type="button" onClick={() => mutation.mutate()}>
        Start user A mutation
      </button>
      <button type="button" onClick={() => currentUser.refetch()}>
        Refresh mutation identity
      </button>
    </div>
  );
}

function SignOutBoundaryProbe() {
  const currentUser = useCurrentUser();
  const signOut = useSignOut();
  const sensitiveQuery = useQuery({
    queryKey: ['sign-out-sensitive-state'],
    queryFn: async () => {
      const response = await fetch('/api/v1/sign-out-sensitive-state');
      return (await response.json()) as { marker: string };
    },
    retry: false,
  });

  return (
    <div>
      <span data-testid="signed-in-identity">{currentUser.data?.data?.id ?? 'anonymous'}</span>
      <span data-testid="sensitive-marker">{sensitiveQuery.data?.marker}</span>
      {signOut.isError && <span role="alert">Sign out failed; retry</span>}
      <button type="button" onClick={() => signOut.mutate()}>
        Sign out
      </button>
    </div>
  );
}

function AuthSwitchProbe() {
  const currentUser = useCurrentUser();
  const signIn = useSignIn();
  const signOut = useSignOut();
  const featureState = useQuery({
    queryKey: ['auth-switch-feature-state'],
    queryFn: async () => {
      const response = await fetch('/api/v1/auth-switch-feature-state');
      return (await response.json()) as { owner: string };
    },
    enabled: currentUser.data?.data !== undefined,
    retry: false,
  });

  return (
    <div>
      <span data-testid="switch-identity">{currentUser.data?.data?.id ?? 'anonymous'}</span>
      <span data-testid="switch-feature-owner">{featureState.data?.owner}</span>
      <button type="button" onClick={() => signOut.mutate()}>
        End user A session
      </button>
      <button
        type="button"
        onClick={() => signIn.mutate({ username: 'user-b', password: 'password' })}
      >
        Sign in user B
      </button>
    </div>
  );
}

function SessionExpiryBoundaryProbe() {
  const currentUser = useCurrentUser();
  const sensitiveQuery = useQuery({
    queryKey: ['session-expiry-sensitive-state'],
    queryFn: async () => {
      const response = await fetch('/api/v1/session-expiry-sensitive-state');
      if (!response.ok) {
        throw { status: response.status };
      }
      return (await response.json()) as { marker: string };
    },
    retry: false,
  });

  return (
    <div>
      <span data-testid="expiry-identity">{currentUser.data?.data?.id ?? 'anonymous'}</span>
      <span data-testid="expiry-sensitive-marker">{sensitiveQuery.data?.marker}</span>
      <button type="button" onClick={() => sensitiveQuery.refetch()}>
        Trigger expired request
      </button>
    </div>
  );
}

function SessionExpiryCacheProbe({
  observeFeatureClient,
}: {
  observeFeatureClient: (client: QueryClient) => void;
}) {
  const currentUser = useCurrentUser();
  const signIn = useSignIn();
  const featureClient = useQueryClient();

  useLayoutEffect(() => {
    observeFeatureClient(featureClient);
  }, [featureClient, observeFeatureClient]);

  return (
    <div>
      <span data-testid="expiry-cache-identity">
        {currentUser.data?.data?.id ?? 'anonymous'}
      </span>
      <button
        type="button"
        onClick={() => {
          void currentUser.refetch();
          void Promise.allSettled([
            apiClient.get({ url: '/session-expiry-cache-state', throwOnError: true }),
            apiClient.get({ url: '/session-expiry-cache-state', throwOnError: true }),
          ]);
        }}
      >
        Trigger duplicate expiry
      </button>
      <button
        type="button"
        onClick={() => signIn.mutate({ username: 'user-b', password: 'password' })}
      >
        Sign in replacement user
      </button>
    </div>
  );
}

function PermissionReconciliationProbe() {
  const currentUser = useCurrentUser();
  const privilegedQuery = useQuery({
    queryKey: ['permission-reconciliation-state'],
    queryFn: async () => {
      const response = await fetch('/api/v1/permission-reconciliation-state');
      if (!response.ok) {
        throw { status: response.status };
      }
      return (await response.json()) as { marker: string };
    },
    enabled: currentUser.data?.data?.permissions?.includes('admin.audit.verify') === true,
    retry: false,
  });

  return (
    <div>
      <span data-testid="reconciliation-identity">
        {currentUser.data?.data?.id ?? 'anonymous'}
      </span>
      <span data-testid="reconciliation-permissions">
        {currentUser.data?.data?.permissions?.join(',') ?? ''}
      </span>
      <span data-testid="privileged-marker">{privilegedQuery.data?.marker}</span>
      <button type="button" onClick={() => privilegedQuery.refetch()}>
        Trigger revoked request
      </button>
    </div>
  );
}

function RawClientPermissionProbe() {
  const currentUser = useCurrentUser();
  return (
    <div>
      <span data-testid="raw-client-permissions">
        {currentUser.data?.data?.permissions?.join(',') ?? ''}
      </span>
      <button
        type="button"
        onClick={() => {
          void apiClient
            .get({ url: '/raw-permission-probe', throwOnError: true })
            .catch(() => undefined);
        }}
      >
        Trigger raw forbidden request
      </button>
    </div>
  );
}

describe('QueryProvider session expiry handling', () => {
  beforeEach(() => {
    queryClient.clear();
    window.history.replaceState({}, '', '/history');
  });

  it('isolates feature state when a late user-A request settles after user B replaces the cookie identity', async () => {
    const userAHistory = deferredValue<{ owner: string }>();
    let identity = 'user-a';

    server.use(
      http.get('/api/v1/auth/me', () =>
        HttpResponse.json({
          id: identity,
          username: identity,
          display_name: identity,
          role: 'member',
          role_id: `role-${identity}`,
          role_name: identity,
          permissions: ['query.submit'],
          auth_provider: 'local',
        })
      ),
      http.get('/api/v1/identity-boundary-history', async () => {
        if (identity === 'user-a') {
          return HttpResponse.json(await userAHistory.promise);
        }
        return HttpResponse.json({ owner: 'user-b' });
      })
    );

    const authClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    useUIStore.getState().setActiveSessionId('user-a-session');
    useUIStore.getState().setHoveredSessionId('user-a-hover');
    useUIStore.getState().setPromptDraft('user-a-draft');
    useUIStore.setState({ sidebarCollapsed: true });

    render(
      <QueryProvider client={authClient}>
        <IdentityBoundaryProbe />
      </QueryProvider>
    );

    expect(await screen.findByText('user-a')).toBeInTheDocument();
    identity = 'user-b';
    fireEvent.click(screen.getByRole('button', { name: 'Refresh identity' }));

    await waitFor(() => expect(screen.getByTestId('identity')).toHaveTextContent('user-b'));
    expect(await screen.findByText('user-b', { selector: '[data-testid="history-owner"]' }))
      .toBeInTheDocument();
    expect(screen.getByTestId('active-session')).toHaveTextContent('none');
    expect(screen.getByTestId('hovered-session')).toHaveTextContent('none');
    expect(screen.getByTestId('prompt-draft')).toBeEmptyDOMElement();
    expect(screen.getByTestId('sidebar-collapsed')).toHaveTextContent('true');

    await act(async () => {
      userAHistory.resolve({ owner: 'user-a' });
      await userAHistory.promise;
    });

    expect(screen.getByTestId('history-owner')).toHaveTextContent('user-b');
    expect(screen.getByTestId('feature-cache-owner')).toHaveTextContent('user-b');
    expect(screen.queryByText('user-a', { selector: '[data-testid="history-owner"]' }))
      .not.toBeInTheDocument();
    useUIStore.setState({ sidebarCollapsed: false });
  });

  it('prevents a late user-A mutation from invalidating user-B feature state', async () => {
    const userAMutation = deferredValue<{ ok: boolean }>();
    let identity = 'user-a';
    let userBFeatureRequestCount = 0;
    server.use(
      http.get('/api/v1/auth/me', () =>
        HttpResponse.json({
          id: identity,
          username: identity,
          display_name: identity,
          role: 'member',
          permissions: ['query.submit'],
        })
      ),
      http.get('/api/v1/mutation-boundary-state', () => {
        if (identity === 'user-b') userBFeatureRequestCount += 1;
        return HttpResponse.json({ owner: identity });
      }),
      http.post('/api/v1/late-user-a-mutation', async () =>
        HttpResponse.json(await userAMutation.promise)
      )
    );

    render(
      <QueryProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MutationBoundaryProbe />
      </QueryProvider>
    );

    expect(await screen.findByText('user-a', { selector: '[data-testid="mutation-state-owner"]' }))
      .toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Start user A mutation' }));
    identity = 'user-b';
    fireEvent.click(screen.getByRole('button', { name: 'Refresh mutation identity' }));

    expect(await screen.findByText('user-b', { selector: '[data-testid="mutation-state-owner"]' }))
      .toBeInTheDocument();
    await act(async () => {
      userAMutation.resolve({ ok: true });
      await userAMutation.promise;
    });

    expect(screen.getByTestId('mutation-identity')).toHaveTextContent('user-b');
    expect(screen.getByTestId('mutation-state-owner')).toHaveTextContent('user-b');
    expect(userBFeatureRequestCount).toBe(1);
  });

  it('keeps a truthful retry state without restoring sensitive caches after sign-out fails', async () => {
    const signOutResponse = deferredValue<number>();
    let featureRequestCount = 0;
    server.use(
      http.get('/api/v1/auth/me', () =>
        HttpResponse.json({
          id: 'user-a',
          username: 'user-a',
          display_name: 'User A',
          role: 'member',
          role_id: 'role-a',
          role_name: 'Role A',
          permissions: ['query.submit'],
          auth_provider: 'local',
        })
      ),
      http.get('/api/v1/sign-out-sensitive-state', () => {
        featureRequestCount += 1;
        return HttpResponse.json({
          marker: featureRequestCount === 1 ? 'discarded-user-a-cache' : 'fresh-user-a-state',
        });
      }),
      http.post('/api/v1/auth/sign-out', async () => {
        const status = await signOutResponse.promise;
        return HttpResponse.json(
          { error: 'service_unavailable', message_key: 'error.service_unavailable' },
          { status }
        );
      })
    );

    render(
      <QueryProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <SignOutBoundaryProbe />
      </QueryProvider>
    );

    expect(await screen.findByText('discarded-user-a-cache')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    await waitFor(() => {
      expect(screen.queryByText('discarded-user-a-cache')).not.toBeInTheDocument();
    });

    await act(async () => {
      signOutResponse.resolve(503);
      await signOutResponse.promise;
    });

    expect(await screen.findByRole('alert')).toHaveTextContent('Sign out failed; retry');
    expect(await screen.findByText('fresh-user-a-state')).toBeInTheDocument();
    expect(screen.queryByText('discarded-user-a-cache')).not.toBeInTheDocument();
    expect(screen.getByTestId('signed-in-identity')).toHaveTextContent('user-a');
  });

  it('removes authenticated state and feature caches after sign-out succeeds', async () => {
    let authenticated = true;
    server.use(
      http.get('/api/v1/auth/me', () => {
        if (!authenticated) {
          return HttpResponse.json(
            { error: 'unauthorized', message_key: 'error.unauthorized' },
            { status: 401 }
          );
        }
        return HttpResponse.json({
          id: 'user-a',
          username: 'user-a',
          display_name: 'User A',
          role: 'member',
          role_id: 'role-a',
          role_name: 'Role A',
          permissions: ['query.submit'],
          auth_provider: 'local',
        });
      }),
      http.get('/api/v1/sign-out-sensitive-state', () =>
        HttpResponse.json({ marker: 'user-a-sensitive-state' })
      ),
      http.post('/api/v1/auth/sign-out', () => {
        authenticated = false;
        return new HttpResponse(null, { status: 204 });
      })
    );

    render(
      <QueryProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <SignOutBoundaryProbe />
      </QueryProvider>
    );

    expect(await screen.findByText('user-a-sensitive-state')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));

    await waitFor(() => {
      expect(screen.getByTestId('signed-in-identity')).toHaveTextContent('anonymous');
    });
    expect(screen.queryByText('user-a-sensitive-state')).not.toBeInTheDocument();
  });

  it('starts explicit sign-in with a fresh feature cache for the new identity', async () => {
    let identity: 'user-a' | 'anonymous' | 'user-b' = 'user-a';
    server.use(
      http.get('/api/v1/auth/me', () => {
        if (identity === 'anonymous') {
          return HttpResponse.json(
            { error: 'unauthorized', message_key: 'error.unauthorized' },
            { status: 401 }
          );
        }
        return HttpResponse.json({
          id: identity,
          username: identity,
          display_name: identity,
          role: 'member',
          role_id: `role-${identity}`,
          role_name: identity,
          permissions: ['query.submit'],
          auth_provider: 'local',
        });
      }),
      http.get('/api/v1/auth-switch-feature-state', () =>
        HttpResponse.json({ owner: identity })
      ),
      http.post('/api/v1/auth/sign-out', () => {
        identity = 'anonymous';
        return new HttpResponse(null, { status: 204 });
      }),
      http.post('/api/v1/auth/sign-in', () => {
        identity = 'user-b';
        return HttpResponse.json({
          id: 'user-b',
          username: 'user-b',
          display_name: 'User B',
          role: 'member',
          role_id: 'role-user-b',
          role_name: 'User B',
          permissions: ['query.submit'],
          auth_provider: 'local',
        });
      })
    );

    render(
      <QueryProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <AuthSwitchProbe />
      </QueryProvider>
    );

    expect(await screen.findByText('user-a', { selector: '[data-testid="switch-feature-owner"]' }))
      .toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'End user A session' }));
    await waitFor(() => expect(screen.getByTestId('switch-identity')).toHaveTextContent('anonymous'));

    fireEvent.click(screen.getByRole('button', { name: 'Sign in user B' }));

    await waitFor(() => expect(screen.getByTestId('switch-identity')).toHaveTextContent('user-b'));
    expect(await screen.findByText('user-b', { selector: '[data-testid="switch-feature-owner"]' }))
      .toBeInTheDocument();
    expect(screen.queryByText('user-a', { selector: '[data-testid="switch-feature-owner"]' }))
      .not.toBeInTheDocument();
  });

  it('removes the old identity and feature state when a request reports session expiry', async () => {
    let featureRequestCount = 0;
    server.use(
      http.get('/api/v1/auth/me', () =>
        HttpResponse.json({
          id: 'user-a',
          username: 'user-a',
          display_name: 'User A',
          role: 'member',
          role_id: 'role-a',
          role_name: 'Role A',
          permissions: ['query.submit'],
          auth_provider: 'local',
        })
      ),
      http.get('/api/v1/session-expiry-sensitive-state', () => {
        featureRequestCount += 1;
        if (featureRequestCount > 1) {
          return HttpResponse.json(
            { error: 'unauthorized', message_key: 'error.unauthorized' },
            { status: 401 }
          );
        }
        return HttpResponse.json({ marker: 'expired-user-a-state' });
      })
    );
    window.history.replaceState({}, '', '/history');

    render(
      <QueryProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <SessionExpiryBoundaryProbe />
      </QueryProvider>
    );

    expect(await screen.findByText('expired-user-a-state')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Trigger expired request' }));

    await waitFor(() => expect(window.location.pathname).toBe('/sign-in'));
    expect(window.location.search).toBe('?error=session_expired');
    await waitFor(() => expect(screen.getByTestId('expiry-identity')).toHaveTextContent('anonymous'));
    expect(screen.queryByText('expired-user-a-state')).not.toBeInTheDocument();
  });

  it.each(['injected', 'default'] as const)(
    'removes expired identity caches and ignores late auth settlement with the %s auth client',
    async (clientMode) => {
      const expiredIdentity = {
        id: 'expired-user-id',
        username: 'expired-username',
        display_name: 'Expired User',
        role: 'expired-role',
        role_id: 'expired-role-id',
        role_name: 'Expired Role',
        permissions: ['admin.audit.verify'],
        auth_provider: 'local',
      };
      const replacementIdentity = {
        id: 'replacement-user-id',
        username: 'replacement-username',
        display_name: 'Replacement User',
        role: 'replacement-role',
        role_id: 'replacement-role-id',
        role_name: 'Replacement Role',
        permissions: ['query.history.view'],
        auth_provider: 'local',
      };
      const lateCurrentUser = deferredValue<typeof expiredIdentity>();
      let currentUserRequestCount = 0;
      server.use(
        http.get('/api/v1/auth/me', async () => {
          currentUserRequestCount += 1;
          if (currentUserRequestCount === 1) {
            return HttpResponse.json(expiredIdentity);
          }
          return HttpResponse.json(await lateCurrentUser.promise);
        }),
        http.get('/api/v1/session-expiry-cache-state', () =>
          HttpResponse.json(
            { error: 'unauthorized', message_key: 'error.unauthorized' },
            { status: 401 }
          )
        ),
        http.post('/api/v1/auth/sign-in', () => HttpResponse.json(replacementIdentity))
      );

      const authClient = clientMode === 'default'
        ? queryClient
        : new QueryClient({ defaultOptions: { queries: { retry: false } } });
      const featureClients: QueryClient[] = [];
      const observeFeatureClient = (client: QueryClient) => {
        if (!featureClients.includes(client)) featureClients.push(client);
      };
      useUIStore.getState().setActiveSessionId('expired-session-id');
      useUIStore.getState().setHoveredSessionId('expired-hover-id');
      useUIStore.getState().setPromptDraft('expired prompt');
      useUIStore.setState({ sidebarCollapsed: true });

      render(
        <QueryProvider client={clientMode === 'injected' ? authClient : undefined}>
          <SessionExpiryCacheProbe observeFeatureClient={observeFeatureClient} />
        </QueryProvider>
      );

      expect(await screen.findByTestId('expiry-cache-identity')).toHaveTextContent(
        expiredIdentity.id
      );
      await waitFor(() => expect(featureClients).toHaveLength(1));
      featureClients[0].setQueryData(['expired-feature-state'], {
        owner: expiredIdentity.id,
      });
      fireEvent.click(screen.getByRole('button', { name: 'Trigger duplicate expiry' }));
      await waitFor(() => expect(currentUserRequestCount).toBe(2));

      await waitFor(() => expect(window.location.pathname).toBe('/sign-in'));
      expect(window.location.search).toBe('?error=session_expired');
      await waitFor(() => {
        expect(authClient.getQueryData(CURRENT_USER_QUERY_KEY)).toBeUndefined();
        expect(
          authClient.getQueryCache().findAll({ queryKey: CURRENT_USER_QUERY_KEY, exact: true })
        ).toHaveLength(0);
      });
      expect(screen.getByTestId('expiry-cache-identity')).toHaveTextContent('anonymous');
      const expiredCacheSnapshot = JSON.stringify(
        authClient.getQueryCache().getAll().map((query) => query.state.data)
      );
      for (const identityValue of [
        expiredIdentity.username,
        expiredIdentity.id,
        expiredIdentity.role,
        expiredIdentity.role_id,
        expiredIdentity.role_name,
        ...expiredIdentity.permissions,
      ]) {
        expect(expiredCacheSnapshot).not.toContain(identityValue);
      }
      expect(featureClients.length).toBeGreaterThan(1);
      for (const featureClient of featureClients) {
        expect(featureClient.getQueryCache().getAll()).toHaveLength(0);
        expect(featureClient.getMutationCache().getAll()).toHaveLength(0);
      }
      expect(useUIStore.getState()).toMatchObject({
        activeSessionId: null,
        hoveredSessionId: null,
        promptDraft: '',
        sidebarCollapsed: true,
      });

      await act(async () => {
        lateCurrentUser.resolve(expiredIdentity);
        await lateCurrentUser.promise;
      });
      await waitFor(() => {
        expect(authClient.getQueryData(CURRENT_USER_QUERY_KEY)).toBeUndefined();
        expect(
          authClient.getQueryCache().findAll({ queryKey: CURRENT_USER_QUERY_KEY, exact: true })
        ).toHaveLength(0);
      });

      fireEvent.click(screen.getByRole('button', { name: 'Sign in replacement user' }));
      await waitFor(() => {
        expect(screen.getByTestId('expiry-cache-identity')).toHaveTextContent(
          replacementIdentity.id
        );
      });
      expect(authClient.getQueryData(CURRENT_USER_QUERY_KEY)).toMatchObject({
        data: replacementIdentity,
      });
      const replacementCacheSnapshot = JSON.stringify(
        authClient.getQueryCache().getAll().map((query) => query.state.data)
      );
      expect(replacementCacheSnapshot).toContain(replacementIdentity.id);
      expect(replacementCacheSnapshot).not.toContain(expiredIdentity.id);
      expect(
        authClient.getQueryCache().findAll({ queryKey: CURRENT_USER_QUERY_KEY, exact: true })
      ).toHaveLength(1);
    }
  );

  it('reconciles a permission-revocation 403 without logging out or retaining privileged state', async () => {
    let permissions = ['admin.audit.verify'];
    let privilegedRequestCount = 0;
    let currentUserRequestCount = 0;
    server.use(
      http.get('/api/v1/auth/me', () => {
        currentUserRequestCount += 1;
        return HttpResponse.json({
          id: 'user-a',
          username: 'user-a',
          display_name: 'User A',
          role: 'member',
          role_id: 'role-a',
          role_name: 'Role A',
          permissions,
          auth_provider: 'local',
        });
      }),
      http.get('/api/v1/permission-reconciliation-state', () => {
        privilegedRequestCount += 1;
        if (privilegedRequestCount > 1) {
          return HttpResponse.json(
            { error: 'forbidden', message_key: 'error.forbidden' },
            { status: 403 }
          );
        }
        return HttpResponse.json({ marker: 'revoked-audit-state' });
      })
    );
    window.history.replaceState({}, '', '/admin/audit');

    render(
      <QueryProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <PermissionReconciliationProbe />
      </QueryProvider>
    );

    expect(await screen.findByText('revoked-audit-state')).toBeInTheDocument();
    permissions = [];
    fireEvent.click(screen.getByRole('button', { name: 'Trigger revoked request' }));

    await waitFor(() => {
      expect(screen.getByTestId('reconciliation-permissions')).toBeEmptyDOMElement();
    });
    expect(screen.getByTestId('reconciliation-identity')).toHaveTextContent('user-a');
    expect(screen.queryByText('revoked-audit-state')).not.toBeInTheDocument();
    expect(window.location.pathname).toBe('/admin/audit');
    expect(currentUserRequestCount).toBe(2);
  });

  it('revalidates permissions before rendering a newly entered protected location', async () => {
    let permissions = ['admin.audit.verify'];
    let currentUserRequestCount = 0;
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    server.use(
      http.get('/api/v1/auth/me', () => {
        currentUserRequestCount += 1;
        return HttpResponse.json({
          id: 'user-a',
          username: 'user-a',
          display_name: 'User A',
          role: 'member',
          role_id: 'role-a',
          role_name: 'Role A',
          permissions,
          auth_provider: 'local',
        });
      }),
      http.get('/api/v1/permission-reconciliation-state', () =>
        HttpResponse.json({ marker: 'protected-audit-state' })
      )
    );

    const { rerender } = render(
      <QueryProvider client={client} authorizationKey="location-a">
        <PermissionReconciliationProbe />
      </QueryProvider>
    );

    expect(await screen.findByText('protected-audit-state')).toBeInTheDocument();
    permissions = [];
    rerender(
      <QueryProvider client={client} authorizationKey="location-b">
        <PermissionReconciliationProbe />
      </QueryProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('reconciliation-permissions')).toBeEmptyDOMElement();
    });
    expect(screen.queryByText('protected-audit-state')).not.toBeInTheDocument();
    expect(currentUserRequestCount).toBe(2);
  });

  it('publishes newly granted permissions on the next protected navigation', async () => {
    let permissions: string[] = [];
    let currentUserRequestCount = 0;
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    server.use(
      http.get('/api/v1/auth/me', () => {
        currentUserRequestCount += 1;
        return HttpResponse.json({
          id: 'user-a',
          username: 'user-a',
          display_name: 'User A',
          role: 'member',
          permissions,
        });
      }),
      http.get('/api/v1/permission-reconciliation-state', () =>
        HttpResponse.json({ marker: 'newly-granted-audit-state' })
      )
    );

    const { rerender } = render(
      <QueryProvider client={client} authorizationKey="location-a">
        <PermissionReconciliationProbe />
      </QueryProvider>
    );
    expect(await screen.findByTestId('reconciliation-permissions')).toBeEmptyDOMElement();

    permissions = ['admin.audit.verify'];
    rerender(
      <QueryProvider client={client} authorizationKey="location-b">
        <PermissionReconciliationProbe />
      </QueryProvider>
    );

    expect(await screen.findByText('newly-granted-audit-state')).toBeInTheDocument();
    expect(currentUserRequestCount).toBe(2);
  });

  it('fails closed without logging out when authorization revalidation cannot be verified', async () => {
    let currentUserRequestCount = 0;
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    server.use(
      http.get('/api/v1/auth/me', () => {
        currentUserRequestCount += 1;
        if (currentUserRequestCount > 1) {
          return HttpResponse.json(
            { error: 'service_unavailable', message_key: 'error.service_unavailable' },
            { status: 503 }
          );
        }
        return HttpResponse.json({
          id: 'user-a',
          username: 'user-a',
          display_name: 'User A',
          role: 'member',
          permissions: ['admin.audit.verify'],
        });
      }),
      http.get('/api/v1/permission-reconciliation-state', () =>
        HttpResponse.json({ marker: 'unverified-audit-state' })
      )
    );

    const { rerender } = render(
      <QueryProvider client={client} authorizationKey="location-a">
        <PermissionReconciliationProbe />
      </QueryProvider>
    );
    expect(await screen.findByText('unverified-audit-state')).toBeInTheDocument();

    rerender(
      <QueryProvider client={client} authorizationKey="location-b">
        <PermissionReconciliationProbe />
      </QueryProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('reconciliation-permissions')).toBeEmptyDOMElement();
    });
    expect(screen.getByTestId('reconciliation-identity')).toHaveTextContent('user-a');
    expect(screen.queryByText('unverified-audit-state')).not.toBeInTheDocument();
    expect(currentUserRequestCount).toBe(2);
  });

  it('reconciles a raw generated-client 403 outside TanStack Query', async () => {
    let permissions = ['admin.audit.verify'];
    let currentUserRequestCount = 0;
    server.use(
      http.get('/api/v1/auth/me', () => {
        currentUserRequestCount += 1;
        return HttpResponse.json({
          id: 'user-a',
          username: 'user-a',
          display_name: 'User A',
          role: 'member',
          permissions,
        });
      }),
      http.get('/api/v1/raw-permission-probe', () =>
        HttpResponse.json(
          { error: 'forbidden', message_key: 'error.forbidden' },
          { status: 403 }
        )
      )
    );

    render(
      <QueryProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <RawClientPermissionProbe />
      </QueryProvider>
    );

    expect(await screen.findByTestId('raw-client-permissions')).toHaveTextContent(
      'admin.audit.verify'
    );
    permissions = [];
    fireEvent.click(screen.getByRole('button', { name: 'Trigger raw forbidden request' }));

    await waitFor(() => {
      expect(screen.getByTestId('raw-client-permissions')).toBeEmptyDOMElement();
    });
    expect(currentUserRequestCount).toBe(2);
  });

  afterEach(() => {
    queryClient.clear();
    useUIStore.setState({ sidebarCollapsed: false });
    useUIStore.getState().resetIdentityState();
  });

  it('redirects rejected authenticated queries with a sanitized session error code', async () => {
    render(
      <QueryProvider>
        <ExpiredSessionProbe />
      </QueryProvider>
    );

    await waitFor(() => {
      expect(window.location.pathname).toBe('/sign-in');
      expect(window.location.search).toBe('?error=session_expired');
    });
  });

  it('preserves an explicit SSO callback error on the sign-in route', async () => {
    window.history.replaceState({}, '', '/sign-in?error=sso_validation_failed');

    render(
      <QueryProvider>
        <ExpiredSessionProbe />
      </QueryProvider>
    );

    await screen.findByTestId('query-rejected');

    expect(window.location.pathname).toBe('/sign-in');
    expect(window.location.search).toBe('?error=sso_validation_failed');
  });
});

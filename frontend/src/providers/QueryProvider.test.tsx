import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, useQuery, useQueryClient } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { QueryProvider, queryClient } from './QueryProvider';
import { useCurrentUser, useSignIn, useSignOut } from '../hooks/useAuth';
import { useUIStore } from '../stores/uiStore';
import { http, HttpResponse } from 'msw';
import { server } from '../test/server';

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
      <span data-testid="feature-cache-owner">
        {featureClient.getQueryData<{ owner: string }>(['identity-boundary-history'])?.owner}
      </span>
      <button type="button" onClick={() => currentUser.refetch()}>
        Refresh identity
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

    await act(async () => {
      userAHistory.resolve({ owner: 'user-a' });
      await userAHistory.promise;
    });

    expect(screen.getByTestId('history-owner')).toHaveTextContent('user-b');
    expect(screen.getByTestId('feature-cache-owner')).toHaveTextContent('user-b');
    expect(screen.queryByText('user-a', { selector: '[data-testid="history-owner"]' }))
      .not.toBeInTheDocument();
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

  afterEach(() => {
    queryClient.clear();
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

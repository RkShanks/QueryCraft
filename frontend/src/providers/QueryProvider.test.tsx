import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, useQuery, useQueryClient } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { QueryProvider, queryClient } from './QueryProvider';
import { useCurrentUser } from '../hooks/useAuth';
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

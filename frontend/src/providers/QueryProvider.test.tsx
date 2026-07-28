import { render, screen, waitFor } from '@testing-library/react';
import { useQuery } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { QueryProvider, queryClient } from './QueryProvider';

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
  return query.isError ? <span>query rejected</span> : null;
}

describe('QueryProvider session expiry handling', () => {
  beforeEach(() => {
    queryClient.clear();
    window.history.replaceState({}, '', '/history');
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

    await screen.findByText('query rejected');

    expect(window.location.pathname).toBe('/sign-in');
    expect(window.location.search).toBe('?error=sso_validation_failed');
  });
});

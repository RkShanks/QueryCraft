import { render, waitFor } from '@testing-library/react';
import { useQuery } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { QueryProvider, queryClient } from './QueryProvider';

function ExpiredSessionProbe() {
  useQuery({
    queryKey: ['expired-session-probe'],
    queryFn: async () => {
      throw { status: 401 };
    },
    retry: false,
  });
  return null;
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
});

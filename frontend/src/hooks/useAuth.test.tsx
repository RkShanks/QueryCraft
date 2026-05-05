import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useSignIn, useCurrentUser, useSignOut } from './useAuth';
import { createWrapper } from '../test/utils';
import { server } from '../test/server';
import { http, HttpResponse } from 'msw';

describe('Auth Hooks', () => {
  describe('useSignIn', () => {
    it('should sign in successfully', async () => {
      const { result } = renderHook(() => useSignIn(), { wrapper: createWrapper() });
      
      result.current.mutate({ username: 'admin', password: 'password' });
      
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.data?.username).toBe('admin');
    });

    it('should handle 401 invalid credentials', async () => {
      server.use(
        http.post('/api/v1/auth/sign-in', () => {
          return HttpResponse.json({ error: 'unauthorized', message_key: 'auth.signIn.error.invalidCredentials' }, { status: 401 });
        })
      );

      const { result } = renderHook(() => useSignIn(), { wrapper: createWrapper() });
      
      result.current.mutate({ username: 'admin', password: 'wrong' });
      
      await waitFor(() => expect(result.current.isError).toBe(true));
    });
  });

  describe('useCurrentUser', () => {
    it('should fetch current user', async () => {
      const { result } = renderHook(() => useCurrentUser(), { wrapper: createWrapper() });
      
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.data?.username).toBe('admin');
    });

    it('should handle 401 not authenticated', async () => {
      server.use(
        http.get('/api/v1/auth/me', () => {
          return HttpResponse.json({ error: 'unauthorized', message_key: 'error.unauthorized' }, { status: 401 });
        })
      );

      const { result } = renderHook(() => useCurrentUser(), { wrapper: createWrapper() });
      
      await waitFor(() => expect(result.current.isError).toBe(true));
    });
  });

  describe('useSignOut', () => {
    it('should sign out successfully', async () => {
      const { result } = renderHook(() => useSignOut(), { wrapper: createWrapper() });
      
      result.current.mutate();
      
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
    });
  });
});

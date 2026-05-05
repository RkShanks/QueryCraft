import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useSubmitQuestion, useAcceptQuery, useHistory } from './useQuerySubmit';
import { createWrapper } from '../test/utils';
import { server } from '../test/server';
import { http, HttpResponse } from 'msw';

describe('Query Hooks', () => {
  describe('useSubmitQuestion', () => {
    it('should submit a question successfully', async () => {
      const { result } = renderHook(() => useSubmitQuestion(), { wrapper: createWrapper() });
      
      result.current.mutate({ question: 'How many users?' });
      
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.kind).toBe('result');
      expect(result.current.data?.attempt_id).toBe('a1b2c3d4-5e6f-4a5b-8c7d-9e0f1a2b3c4d');
    });

    it('should handle 400 validation error', async () => {
      server.use(
        http.post('/api/v1/query/submit', () => {
          return HttpResponse.json({ error: 'validation', message_key: 'error.validation.questionEmpty' }, { status: 400 });
        })
      );

      const { result } = renderHook(() => useSubmitQuestion(), { wrapper: createWrapper() });
      result.current.mutate({ question: '' });
      
      await waitFor(() => expect(result.current.isError).toBe(true));
    });
  });

  describe('useAcceptQuery', () => {
    it('should accept a query successfully', async () => {
      const { result } = renderHook(() => useAcceptQuery(), { wrapper: createWrapper() });
      
      result.current.mutate({ attempt_id: 'a1b2c3d4-5e6f-4a5b-8c7d-9e0f1a2b3c4d' });
      
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.id).toBe('f9e8d7c6-b5a4-4c3b-2a1d-0e9f8d7c6b5a');
    });
  });

  describe('useHistory', () => {
    it('should fetch history successfully', async () => {
      const { result } = renderHook(() => useHistory(), { wrapper: createWrapper() });
      
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.items).toHaveLength(1);
    });
  });
});

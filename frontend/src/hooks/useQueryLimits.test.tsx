import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../test/server';
import { createWrapper } from '../test/utils';
import { useQueryLimits } from './useQueryLimits';

describe('useQueryLimits', () => {
  it('loads the configured positive question limit', async () => {
    server.use(
      http.get('/api/v1/query/limits', () =>
        HttpResponse.json({ max_question_length: 37 })
      )
    );

    const { result } = renderHook(() => useQueryLimits(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ max_question_length: 37 });
  });

  it.each([
    ['missing', {}],
    ['zero', { max_question_length: 0 }],
    ['negative', { max_question_length: -1 }],
    ['fractional', { max_question_length: 3.5 }],
    ['string', { max_question_length: '37' }],
  ])('fails closed for a %s limit response', async (_caseName, responseBody) => {
    server.use(
      http.get('/api/v1/query/limits', () => HttpResponse.json(responseBody))
    );

    const { result } = renderHook(() => useQueryLimits(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
  });

  it('recovers when an explicit retry returns a valid limit', async () => {
    let requestCount = 0;
    server.use(
      http.get('/api/v1/query/limits', () => {
        requestCount += 1;
        if (requestCount === 1) {
          return HttpResponse.json(
            { error: 'service_unavailable', message_key: 'error.service_unavailable' },
            { status: 503 }
          );
        }
        return HttpResponse.json({ max_question_length: 37 });
      })
    );

    const { result } = renderHook(() => useQueryLimits(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.isError).toBe(true));

    await result.current.refetch();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ max_question_length: 37 });
    expect(requestCount).toBe(2);
  });
});

import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useAdminAudit } from './useAdminAudit';
import { createWrapper } from '../test/utils';
import { server } from '../test/server';
import { http, HttpResponse } from 'msw';

describe('useAdminAudit Hook', () => {
  it('should fetch audit status successfully', async () => {
    server.use(
      http.get('/api/v1/admin/audit/status', () => {
        return HttpResponse.json({
          total_entries: 15,
          last_verification: {
            verified: true,
            entries_checked: 10,
            first_break_at: null,
            verified_at: '2026-06-07T00:00:00Z',
          },
        });
      })
    );

    const { result } = renderHook(() => useAdminAudit(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.statusQuery.isSuccess).toBe(true));
    expect(result.current.statusQuery.data?.total_entries).toBe(15);
    expect(result.current.statusQuery.data?.last_verification?.verified).toBe(true);
  });

  it('should verify audit chain successfully', async () => {
    let verifiedCount = 0;
    server.use(
      http.post('/api/v1/admin/audit/verify', () => {
        verifiedCount++;
        return HttpResponse.json({
          verified: true,
          entries_checked: 15,
          first_break_at: null,
          verified_at: '2026-06-07T00:01:00Z',
        });
      })
    );

    const { result } = renderHook(() => useAdminAudit(), { wrapper: createWrapper() });

    result.current.verifyMutation.mutate();

    await waitFor(() => expect(result.current.verifyMutation.isSuccess).toBe(true));
    expect(result.current.verifyMutation.data?.verified).toBe(true);
    expect(verifiedCount).toBe(1);
  });
});

import { fireEvent, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { AdminQuotasPage } from './AdminQuotasPage';
import { server } from '../test/server';
import { renderWithClient } from '../test/utils';

const quotaOnlyUser = {
  id: 'quota-admin-id',
  username: 'quota-admin',
  display_name: 'Quota Admin',
  role: 'custom',
  permissions: ['admin.quotas.manage'],
};

const configuredQuota = {
  role_id: 'analyst-role-id',
  role_name: 'analyst',
  daily_query_limit: 100,
  daily_execution_limit: 50,
  daily_export_limit: 5,
};

const configuredStatus = {
  role_id: 'analyst-role-id',
  role_name: 'analyst',
  dimensions: {
    queries: { limit: 100, used: 42, remaining: 58 },
    executions: { limit: 50, used: 10, remaining: 40 },
    exports: { limit: 5, used: 1, remaining: 4 },
  },
  reset_at: '2026-07-29T00:00:00Z',
};

function installQuotaOnlyHandlers(
  quotas: unknown[] = [configuredQuota],
  status: unknown[] = [configuredStatus]
) {
  server.use(
    http.get('/api/v1/auth/me', () => HttpResponse.json(quotaOnlyUser)),
    http.get('/api/v1/admin/quotas', () => HttpResponse.json({ quotas })),
    http.get('/api/v1/admin/quotas/status', () => HttpResponse.json({ status }))
  );
}

describe('AdminQuotasPage Phase 6A regressions', () => {
  it('P6-FR-149 shows quota-only empty states without requesting role or SSO data', async () => {
    let rolesRequested = false;
    let mappingsRequested = false;
    installQuotaOnlyHandlers([], []);
    server.use(
      http.get('/api/v1/admin/roles', () => {
        rolesRequested = true;
        return HttpResponse.json({ roles: [] });
      }),
      http.get('/api/v1/admin/sso/group-mappings', () => {
        mappingsRequested = true;
        return HttpResponse.json({ mappings: [] });
      })
    );

    renderWithClient(<AdminQuotasPage />);

    expect(await screen.findByText('No quota configurations yet.')).toBeInTheDocument();
    expect(screen.getByText('No quota usage to display.')).toBeInTheDocument();
    expect(rolesRequested).toBe(false);
    expect(mappingsRequested).toBe(false);
  });

  it.each([
    {
      status: 403,
      body: { error: 'forbidden', message_key: 'error.forbidden' },
      message: 'This request was blocked for security reasons.',
    },
    {
      status: 503,
      body: { error: 'service_unavailable', message_key: 'error.service_unavailable' },
      message: 'Service temporarily unavailable. Please try again later.',
    },
  ])(
    'P6-FR-149 renders the localized $status quota API state',
    async ({ status, body, message }) => {
      server.use(
        http.get('/api/v1/auth/me', () => HttpResponse.json(quotaOnlyUser)),
        http.get('/api/v1/admin/quotas', () => HttpResponse.json(body, { status })),
        http.get('/api/v1/admin/quotas/status', () => HttpResponse.json(body, { status }))
      );

      renderWithClient(<AdminQuotasPage />);

      await waitFor(() => {
        expect(screen.getAllByText(message)).toHaveLength(2);
      });
    }
  );

  it.each(['-1', '1.5', '9007199254740992'])(
    'P6-FR-149 rejects invalid quota value %s before the API request',
    async (invalidLimit) => {
      let updateRequests = 0;
      installQuotaOnlyHandlers();
      server.use(
        http.put('/api/v1/admin/quotas/:roleId', () => {
          updateRequests += 1;
          return HttpResponse.json(configuredQuota);
        })
      );

      renderWithClient(<AdminQuotasPage />);
      fireEvent.click(await screen.findByTestId('edit-quota-analyst-role-id'));

      const queryLimitInput = screen.getByLabelText('Daily Query Limit');
      fireEvent.change(queryLimitInput, { target: { value: invalidLimit } });
      fireEvent.submit(queryLimitInput.closest('form')!);

      expect(
        screen.getByText('Enter a non-negative whole number within the supported range.')
      ).toBeInTheDocument();
      expect(updateRequests).toBe(0);
    }
  );
});

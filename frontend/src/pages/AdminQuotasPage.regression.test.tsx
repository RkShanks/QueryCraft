import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminQuotasPage } from './AdminQuotasPage';
import { server } from '../test/server';
import { renderWithClient } from '../test/utils';
import { PERMISSIONS } from '../auth/permissions';
import i18n from '../i18n';

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

const pendingResponse = {
  error: 'quota_sync_pending',
  message_key: 'error.quota_sync_pending',
  mutation_applied: true,
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

function renderQuotaOnlyPage() {
  return renderWithClient(
    <AdminQuotasPage />,
    [PERMISSIONS.ADMIN_QUOTAS_MANAGE]
  );
}

describe('AdminQuotasPage Phase 6A regressions', () => {
  beforeEach(async () => {
    sessionStorage.clear();
    await i18n.changeLanguage('en');
  });

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

    renderQuotaOnlyPage();

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

      renderQuotaOnlyPage();

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

      renderQuotaOnlyPage();
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

  it('P6-FR-149 exposes complete compact quota summaries for narrow layouts', async () => {
    installQuotaOnlyHandlers();

    renderQuotaOnlyPage();

    const configSummary = await screen.findByRole('article', {
      name: 'analyst quota configuration',
    });
    expect(within(configSummary).getByText('Daily Query Limit')).toBeInTheDocument();
    expect(within(configSummary).getByText('Daily SQL Execution Limit')).toBeInTheDocument();
    expect(within(configSummary).getByText('Daily Audit Export Limit')).toBeInTheDocument();
    expect(within(configSummary).getByTitle('Edit')).toBeInTheDocument();
    expect(within(configSummary).getByTitle('Reset to uncapped')).toBeInTheDocument();

    const statusSummary = screen.getByRole('article', {
      name: 'analyst quota status',
    });
    expect(within(statusSummary).getByText('Resets at')).toBeInTheDocument();
  });

  it('refetches an applied save, suppresses duplicate clicks, and retries without a premature success', async () => {
    let authoritativeQuota = configuredQuota;
    let listRequests = 0;
    const putBodies: unknown[] = [];
    installQuotaOnlyHandlers();
    server.use(
      http.get('/api/v1/admin/quotas', () => {
        listRequests += 1;
        return HttpResponse.json({ quotas: [authoritativeQuota] });
      }),
      http.put('/api/v1/admin/quotas/:roleId', async ({ request }) => {
        putBodies.push(await request.json());
        authoritativeQuota = { ...configuredQuota, daily_query_limit: 4 };
        if (putBodies.length === 1) {
          return HttpResponse.json(pendingResponse, { status: 503 });
        }
        return HttpResponse.json(authoritativeQuota);
      })
    );

    renderQuotaOnlyPage();
    fireEvent.click(await screen.findByTestId('edit-quota-analyst-role-id'));
    fireEvent.change(screen.getByLabelText('Daily Query Limit'), {
      target: { value: '4' },
    });
    const saveButton = screen.getByRole('button', { name: 'Save' });
    fireEvent.click(saveButton);
    fireEvent.click(saveButton);

    const recovery = await screen.findByRole('alert', {
      name: 'Quota change needs synchronization',
    });
    expect(putBodies).toHaveLength(1);
    expect(within(recovery).getByRole('button', { name: 'Retry' })).toBeEnabled();
    expect(screen.queryByText('Changes saved successfully')).not.toBeInTheDocument();
    await waitFor(() => expect(listRequests).toBeGreaterThanOrEqual(2));
    expect(screen.getAllByText('4').length).toBeGreaterThan(0);

    fireEvent.click(within(recovery).getByRole('button', { name: 'Retry' }));

    await waitFor(() => expect(putBodies).toHaveLength(2));
    expect(putBodies[1]).toEqual(putBodies[0]);
    await waitFor(() => {
      expect(
        screen.queryByRole('alert', { name: 'Quota change needs synchronization' })
      ).not.toBeInTheDocument();
    });
    expect(await screen.findByText('Changes saved successfully')).toBeInTheDocument();
  });

  it('restores an applied delete after reload and retries it accessibly in Arabic', async () => {
    let authoritativeQuotas: unknown[] = [configuredQuota];
    let deleteRequests = 0;
    let listRequests = 0;
    installQuotaOnlyHandlers();
    server.use(
      http.get('/api/v1/admin/quotas', () => {
        listRequests += 1;
        return HttpResponse.json({ quotas: authoritativeQuotas });
      }),
      http.delete('/api/v1/admin/quotas/:roleId', () => {
        deleteRequests += 1;
        authoritativeQuotas = [];
        if (deleteRequests === 1) {
          return HttpResponse.json(pendingResponse, { status: 503 });
        }
        return new HttpResponse(null, { status: 204 });
      })
    );
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    await i18n.changeLanguage('ar');

    const firstRender = renderQuotaOnlyPage();
    fireEvent.click(
      await screen.findByTestId('delete-quota-analyst-role-id')
    );
    expect(
      await screen.findByRole('alert', { name: 'تغيير الحصة يحتاج إلى مزامنة' })
    ).toBeInTheDocument();
    await waitFor(() => expect(listRequests).toBeGreaterThanOrEqual(2));
    expect(screen.queryByText('تم حفظ التغييرات بنجاح')).not.toBeInTheDocument();

    firstRender.unmount();
    renderQuotaOnlyPage();

    const restoredRecovery = await screen.findByRole('alert', {
      name: 'تغيير الحصة يحتاج إلى مزامنة',
    });
    expect(screen.getByText('لا توجد تكوينات حصص بعد.')).toBeInTheDocument();
    fireEvent.click(
      within(restoredRecovery).getByRole('button', { name: 'إعادة المحاولة' })
    );

    await waitFor(() => expect(deleteRequests).toBe(2));
    await waitFor(() => {
      expect(
        screen.queryByRole('alert', { name: 'تغيير الحصة يحتاج إلى مزامنة' })
      ).not.toBeInTheDocument();
    });
    expect(await screen.findByText('تم حذف تكوين الحصص بنجاح')).toBeInTheDocument();
  });

  it('distinguishes an ordinary mutation failure and keeps configuration when status fails', async () => {
    let listRequests = 0;
    server.use(
      http.get('/api/v1/auth/me', () => HttpResponse.json(quotaOnlyUser)),
      http.get('/api/v1/admin/quotas', () => {
        listRequests += 1;
        return HttpResponse.json({ quotas: [configuredQuota] });
      }),
      http.get('/api/v1/admin/quotas/status', () =>
        HttpResponse.json(
          { error: 'service_unavailable', message_key: 'error.service_unavailable' },
          { status: 503 }
        )
      ),
      http.put('/api/v1/admin/quotas/:roleId', () =>
        HttpResponse.json(
          { error: 'service_unavailable', message_key: 'error.service_unavailable' },
          { status: 503 }
        )
      )
    );

    renderQuotaOnlyPage();
    const configSummary = await screen.findByRole('article', {
      name: 'analyst quota configuration',
    });
    expect(configSummary).toBeInTheDocument();
    expect(
      await screen.findByText('Service temporarily unavailable. Please try again later.')
    ).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('edit-quota-analyst-role-id'));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(listRequests).toBeGreaterThanOrEqual(2));
    expect(
      screen.queryByRole('alert', { name: 'Quota change needs synchronization' })
    ).not.toBeInTheDocument();
    expect(
      screen.getAllByText('Service temporarily unavailable. Please try again later.')
        .length
    ).toBeGreaterThanOrEqual(2);
    expect(configSummary).toBeInTheDocument();
  });
});

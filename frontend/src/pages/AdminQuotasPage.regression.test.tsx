import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminQuotasPage } from './AdminQuotasPage';
import { server } from '../test/server';
import { renderWithClient } from '../test/utils';
import { PERMISSIONS } from '../auth/permissions';
import i18n from '../i18n';
import type {
  RoleQuotaConfig,
  RoleQuotaStatus,
  UserProfile,
} from '../api/generated/types.gen';

const ANALYST_ROLE_ID = 'd290f1ee-6c54-4b01-90e6-d701748f0851';
const VIEWER_ROLE_ID = '1cbb6f73-7b45-4f43-b052-c3ea6995ff7e';

const quotaOnlyUser = {
  id: 'cfc5034b-6f06-4567-a9ea-b8fcece8d0cc',
  username: 'quota-admin',
  display_name: 'Quota Admin',
  role: 'custom',
  permissions: ['admin.quotas.manage'],
} satisfies UserProfile;

const configuredQuota = {
  role_id: ANALYST_ROLE_ID,
  role_name: 'analyst',
  daily_query_limit: 100,
  daily_execution_limit: 50,
  daily_export_limit: 5,
  created_at: '2026-07-28T00:00:00Z',
  updated_at: '2026-07-29T00:00:00Z',
} satisfies RoleQuotaConfig;

const configuredStatus = {
  role_id: ANALYST_ROLE_ID,
  role_name: 'analyst',
  dimensions: {
    queries: { limit: 100, used: 42, remaining: 58 },
    executions: { limit: 50, used: 10, remaining: 40 },
    exports: { limit: 5, used: 1, remaining: 4 },
  },
  reset_at: '2026-07-29T00:00:00Z',
} satisfies RoleQuotaStatus;

const viewerStatus = {
  ...configuredStatus,
  role_id: VIEWER_ROLE_ID,
  role_name: 'viewer',
} satisfies RoleQuotaStatus;

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
    http.get('/api/v1/admin/quotas/status', () =>
      HttpResponse.json({ status, total: status.length, next_cursor: null })
    )
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
      expectedCount: 2,
    },
    {
      status: 503,
      body: { error: 'service_unavailable', message_key: 'error.service_unavailable' },
      message: 'Service temporarily unavailable. Please try again later.',
      expectedCount: 1,
    },
  ])(
    'P6-FR-149 renders the localized $status quota API state',
    async ({ status, body, message, expectedCount }) => {
      server.use(
        http.get('/api/v1/auth/me', () => HttpResponse.json(quotaOnlyUser)),
        http.get('/api/v1/admin/quotas', () =>
          status === 503
            ? HttpResponse.json({ quotas: [] })
            : HttpResponse.json(body, { status })
        ),
        http.get('/api/v1/admin/quotas/status', () => HttpResponse.json(body, { status }))
      );

      renderQuotaOnlyPage();

      await waitFor(() => {
        expect(screen.getAllByText(message)).toHaveLength(expectedCount);
      });
    }
  );

  it.each([
    ['en', 'Load more quota status'],
    ['ar', 'تحميل المزيد من حالة الحصص'],
  ])('loads and deduplicates quota status pages explicitly in %s', async (language, label) => {
    const requestedCursors: Array<string | null> = [];
    let rolesRequested = false;
    let mappingsRequested = false;
    installQuotaOnlyHandlers();
    server.use(
      http.get('/api/v1/admin/quotas/status', ({ request }) => {
        const cursor = new URL(request.url).searchParams.get('cursor');
        requestedCursors.push(cursor);
        if (cursor === 'viewer-page') {
          return HttpResponse.json({
            status: [configuredStatus, viewerStatus],
            total: 2,
            next_cursor: null,
          });
        }
        return HttpResponse.json({
          status: [configuredStatus],
          total: 2,
          next_cursor: 'viewer-page',
        });
      }),
      http.get('/api/v1/admin/roles', () => {
        rolesRequested = true;
        return HttpResponse.json({ roles: [] });
      }),
      http.get('/api/v1/admin/sso/group-mappings', () => {
        mappingsRequested = true;
        return HttpResponse.json({ mappings: [] });
      })
    );
    await i18n.changeLanguage(language);

    try {
      renderQuotaOnlyPage();
      const loadMore = await screen.findByRole('button', { name: label });
      expect(requestedCursors).toEqual([null]);
      fireEvent.click(loadMore);

      expect(
        await screen.findByRole('article', {
          name: language === 'ar' ? 'حالة حصص الدور viewer' : 'viewer quota status',
        })
      ).toBeInTheDocument();
      expect(
        screen.getAllByRole('article', {
          name: language === 'ar' ? 'حالة حصص الدور analyst' : 'analyst quota status',
        })
      ).toHaveLength(1);
      expect(requestedCursors).toEqual([null, 'viewer-page']);
      expect(rolesRequested).toBe(false);
      expect(mappingsRequested).toBe(false);
    } finally {
      await i18n.changeLanguage('en');
    }
  });

  it('retries a failed quota-status page without hiding quota configuration', async () => {
    let statusRequests = 0;
    installQuotaOnlyHandlers();
    server.use(
      http.get('/api/v1/admin/quotas/status', () => {
        statusRequests += 1;
        if (statusRequests === 1) {
          return HttpResponse.json(
            { error: 'service_unavailable', message_key: 'error.service_unavailable' },
            { status: 503 }
          );
        }
        return HttpResponse.json({
          status: [configuredStatus],
          total: 1,
          next_cursor: null,
        });
      })
    );

    renderQuotaOnlyPage();
    expect(
      await screen.findByRole('article', { name: 'analyst quota configuration' })
    ).toBeInTheDocument();
    const error = await screen.findByText(
      'Service temporarily unavailable. Please try again later.'
    );
    const alert = error.closest('[role="alert"]');
    expect(alert).not.toBeNull();
    fireEvent.click(within(alert as HTMLElement).getByRole('button', { name: 'Retry' }));

    expect(
      await screen.findByRole('article', { name: 'analyst quota status' })
    ).toBeInTheDocument();
    expect(statusRequests).toBe(2);
  });

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
      fireEvent.click(await screen.findByTestId(`edit-quota-${ANALYST_ROLE_ID}`));

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
    fireEvent.click(await screen.findByTestId(`edit-quota-${ANALYST_ROLE_ID}`));
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
      await screen.findByTestId(`delete-quota-${ANALYST_ROLE_ID}`)
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

    fireEvent.click(screen.getByTestId(`edit-quota-${ANALYST_ROLE_ID}`));
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

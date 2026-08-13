/* eslint-disable local/no-inline-user-strings */
import { QueryClient } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { useState } from 'react';
import { QueryProvider } from '../providers/QueryProvider';
import { server } from '../test/server';
import { useAdminAudit } from './useAdminAudit';
import { useAdminDetection } from './useAdminDetection';
import { useAdminQuotas } from './useAdminQuotas';
import { useAdminRole, useAdminRoles } from './useAdminRoles';
import { useAdminSettings } from './useAdminSettings';
import { useAdminSso } from './useAdminSso';
import { useConnections } from './useConnections';
import { useConnectionSchema } from './useConnectionSchema';
import { useHistory, useHistoryDetail } from './useHistory';
import { useQueryLimits } from './useQueryLimits';
import { useSessionDetail, useSessionsList } from './useSessions';
import { useCreateSession, useDeleteSession } from './useSessions';
import { useAcceptQuery, useSubmitQuestion } from './useQuerySubmit';
import { useUpdateFeedback } from './useFeedback';
import { useUserConnections } from './useUserConnections';
import { PERMISSIONS, type Permission } from '../auth/permissions';
import {
  getSessionDeletionVersion,
  resetSessionDeletionLifecycle,
} from '../sessionDeletionLifecycle';

const exactRequestCases: Array<[Permission, string[]]> = [
  [
    PERMISSIONS.QUERY_SUBMIT,
    [
      '/api/v1/connections',
      '/api/v1/query/limits',
      '/api/v1/sessions',
      '/api/v1/sessions/session-id',
    ],
  ],
  [
    PERMISSIONS.QUERY_HISTORY_VIEW,
    ['/api/v1/history', '/api/v1/history/history-id'],
  ],
  [
    PERMISSIONS.ADMIN_CONNECTIONS_MANAGE,
    [
      '/api/v1/admin/connections',
      '/api/v1/admin/connections/connection-id/schema',
      '/api/v1/admin/settings',
    ],
  ],
  [
    PERMISSIONS.ADMIN_ROLES_MANAGE,
    [
      '/api/v1/admin/connections/connection-id/schema',
      '/api/v1/admin/roles',
      '/api/v1/admin/roles/role-id',
      '/api/v1/admin/sso/group-mappings',
    ],
  ],
  [PERMISSIONS.ADMIN_SSO_MANAGE, ['/api/v1/admin/sso/providers']],
  [PERMISSIONS.ADMIN_AUDIT_VERIFY, ['/api/v1/admin/audit/status']],
  [
    PERMISSIONS.ADMIN_QUOTAS_MANAGE,
    ['/api/v1/admin/quotas', '/api/v1/admin/quotas/status'],
  ],
  [PERMISSIONS.ADMIN_SECURITY_MANAGE, ['/api/v1/admin/detection/config']],
];

function PermissionGatingProbe() {
  const sessions = useSessionsList();
  const session = useSessionDetail('session-id');
  const history = useHistory();
  useHistoryDetail('history-id');
  const settings = useAdminSettings();
  const connections = useConnections();
  const roles = useAdminRoles();
  const role = useAdminRole('role-id');
  const sso = useAdminSso();
  const audit = useAdminAudit();
  const quotas = useAdminQuotas();
  const detection = useAdminDetection();
  const schema = useConnectionSchema('connection-id');
  const userConnections = useUserConnections();
  const queryLimits = useQueryLimits();

  const isFetching = [
    sessions,
    session,
    settings,
    connections.listQuery,
    roles.listQuery,
    roles.groupMappingsQuery,
    role,
    sso.listQuery,
    audit.statusQuery,
    quotas.listQuery,
    quotas.statusQuery,
    detection.configQuery,
    schema,
    userConnections,
    queryLimits,
  ].some((query) => query.isFetching) || history.isFetching;

  return <span>{isFetching ? 'fetching' : 'settled'}</span>;
}

function MutationGatingProbe() {
  const [isSettled, setSettled] = useState(false);
  const submit = useSubmitQuestion();
  const accept = useAcceptQuery();
  const createSession = useCreateSession();
  const deleteSession = useDeleteSession();
  const feedback = useUpdateFeedback();

  const triggerRequests = async () => {
    await Promise.allSettled([
      submit.mutateAsync({ question: 'probe', connection_id: 'connection-id' }),
      accept.mutateAsync({ attempt_id: 'attempt-id' }),
      createSession.mutateAsync(),
      deleteSession.mutateAsync('session-id'),
      feedback.mutateAsync({ attemptId: 'attempt-id', feedback: 1 }),
    ]);
    setSettled(true);
  };

  return (
    <button onClick={() => void triggerRequests()}>
      {isSettled ? 'Mutations settled' : 'Trigger mutations'}
    </button>
  );
}

describe('permission-gated feature hooks', () => {
  it('makes zero feature requests when the authenticated user has no permissions', async () => {
    let featureRequestCount = 0;
    server.use(
      http.all('/api/v1/*', ({ request }) => {
        const path = new URL(request.url).pathname;
        if (path === '/api/v1/auth/me') {
          return HttpResponse.json({
            id: 'restricted-user',
            username: 'restricted',
            display_name: 'Restricted',
            role: 'admin',
            role_name: 'admin',
            permissions: [],
          });
        }
        featureRequestCount += 1;
        if (path === '/api/v1/admin/connections') {
          return HttpResponse.json([]);
        }
        if (path === '/api/v1/admin/roles') {
          return HttpResponse.json({ roles: [] });
        }
        if (path === '/api/v1/admin/sso/group-mappings') {
          return HttpResponse.json({ mappings: [] });
        }
        return HttpResponse.json({});
      })
    );

    render(
      <QueryProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <PermissionGatingProbe />
      </QueryProvider>
    );

    expect(await screen.findByText('settled')).toBeInTheDocument();
    expect(featureRequestCount).toBe(0);
  });

  it('rejects imperative feature mutations before they reach the network', async () => {
    resetSessionDeletionLifecycle();
    let featureRequestCount = 0;
    server.use(
      http.all('/api/v1/*', ({ request }) => {
        const path = new URL(request.url).pathname;
        if (path === '/api/v1/auth/me') {
          return HttpResponse.json({
            id: 'restricted-user',
            username: 'restricted',
            display_name: 'Restricted',
            role: 'admin',
            role_name: 'admin',
            permissions: [],
          });
        }
        featureRequestCount += 1;
        return HttpResponse.json({});
      })
    );

    render(
      <QueryProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MutationGatingProbe />
      </QueryProvider>
    );

    fireEvent.click(await screen.findByRole('button', { name: 'Trigger mutations' }));
    await screen.findByRole('button', { name: 'Mutations settled' });
    expect(featureRequestCount).toBe(0);
    expect(getSessionDeletionVersion('session-id')).toBe(0);
  });

  it.each(exactRequestCases)(
    'allows only the exact background requests for %s',
    async (permission, expectedPaths) => {
      const featurePaths = new Set<string>();
      server.use(
        http.all('/api/v1/*', ({ request }) => {
          const path = new URL(request.url).pathname;
          if (path === '/api/v1/auth/me') {
            return HttpResponse.json({
              id: 'exact-permission-user',
              username: 'exact-permission-user',
              display_name: 'Exact Permission User',
              role: 'admin',
              role_name: 'admin',
              permissions: [permission],
            });
          }
          featurePaths.add(path);
          if (path === '/api/v1/admin/connections') {
            return HttpResponse.json([]);
          }
          if (path === '/api/v1/admin/roles') {
            return HttpResponse.json({ roles: [] });
          }
          if (path === '/api/v1/admin/sso/group-mappings') {
            return HttpResponse.json({ mappings: [] });
          }
          if (path === '/api/v1/query/limits') {
            return HttpResponse.json({ max_question_length: 2000 });
          }
          if (path === '/api/v1/sessions') {
            return HttpResponse.json({ items: [], total: 0, next_cursor: null });
          }
          if (path === '/api/v1/sessions/session-id') {
            return HttpResponse.json({
              id: 'session-id',
              connection_id: null,
              preview_text: '',
              created_at: '2026-08-12T00:00:00Z',
              last_activity_at: '2026-08-12T00:00:00Z',
              attempts: [],
              attempts_total: 0,
              attempts_next_cursor: null,
            });
          }
          if (path === '/api/v1/admin/quotas') {
            return HttpResponse.json({ quotas: [] });
          }
          if (path === '/api/v1/admin/quotas/status') {
            return HttpResponse.json({ status: [], total: 0, next_cursor: null });
          }
          return HttpResponse.json({});
        })
      );

      render(
        <QueryProvider
          client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
        >
          <PermissionGatingProbe />
        </QueryProvider>
      );

      expect(await screen.findByText('settled')).toBeInTheDocument();
      expect([...featurePaths].sort()).toEqual([...expectedPaths].sort());
    }
  );
});

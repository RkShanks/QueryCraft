import { QueryClient } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
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
import { useSessionDetail, useSessionsList } from './useSessions';

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
  ].some((query) => query.isFetching) || history.isFetching;

  return <span>{isFetching ? 'fetching' : 'settled'}</span>;
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
          return HttpResponse.json({ connections: [] });
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
});

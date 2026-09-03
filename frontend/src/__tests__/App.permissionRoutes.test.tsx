/* eslint-disable local/no-inline-user-strings */
import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS, type Permission, type ProtectedRoutePath } from '../auth/permissions';
import { queryClient } from '../providers/QueryProvider';
import { server } from '../test/server';
import App from '../App';

vi.mock('../components/shell/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock('../pages/WorkspacePage', () => ({ WorkspacePage: () => <div>workspace-page</div> }));
vi.mock('../pages/AskQuestionPage', () => ({ AskQuestionPage: () => <div>ask-page</div> }));
vi.mock('../pages/HistoryPage', () => ({ default: () => <div>history-page</div> }));
vi.mock('../pages/SettingsPage', () => ({ SettingsPage: () => <div>settings-page</div> }));
vi.mock('../pages/AdminConnectionsPage', () => ({
  AdminConnectionsPage: () => <div>connections-page</div>,
}));
vi.mock('../pages/AdminRolesPage', () => ({ AdminRolesPage: () => <div>roles-page</div> }));
vi.mock('../pages/AdminSsoPage', () => ({ AdminSsoPage: () => <div>sso-page</div> }));
vi.mock('../pages/AdminAuditPage', () => ({ AdminAuditPage: () => <div>audit-page</div> }));
vi.mock('../pages/AdminQuotasPage', () => ({ AdminQuotasPage: () => <div>quotas-page</div> }));
vi.mock('../pages/AdminDetectionPage', () => ({
  AdminDetectionPage: () => <div>detection-page</div>,
}));
vi.mock('../pages/AccessDeniedPage', () => ({
  AccessDeniedPage: () => <div>access-denied-page</div>,
}));

const routeCases: Array<[ProtectedRoutePath, Permission, string]> = [
  ['/', PERMISSIONS.QUERY_SUBMIT, 'workspace-page'],
  ['/ask', PERMISSIONS.QUERY_SUBMIT, 'ask-page'],
  ['/history', PERMISSIONS.QUERY_HISTORY_VIEW, 'history-page'],
  ['/settings', PERMISSIONS.ADMIN_CONNECTIONS_MANAGE, 'settings-page'],
  ['/admin/connections', PERMISSIONS.ADMIN_CONNECTIONS_MANAGE, 'connections-page'],
  ['/admin/roles', PERMISSIONS.ADMIN_ROLES_MANAGE, 'roles-page'],
  ['/admin/sso', PERMISSIONS.ADMIN_SSO_MANAGE, 'sso-page'],
  ['/admin/audit', PERMISSIONS.ADMIN_AUDIT_VERIFY, 'audit-page'],
  ['/admin/quotas', PERMISSIONS.ADMIN_QUOTAS_MANAGE, 'quotas-page'],
  ['/admin/detection', PERMISSIONS.ADMIN_SECURITY_MANAGE, 'detection-page'],
];

const landingCases: Array<[Permission, ProtectedRoutePath, string]> = [
  [PERMISSIONS.QUERY_SUBMIT, '/', 'workspace-page'],
  [PERMISSIONS.QUERY_HISTORY_VIEW, '/history', 'history-page'],
  [PERMISSIONS.ADMIN_CONNECTIONS_MANAGE, '/admin/connections', 'connections-page'],
  [PERMISSIONS.ADMIN_ROLES_MANAGE, '/admin/roles', 'roles-page'],
  [PERMISSIONS.ADMIN_SSO_MANAGE, '/admin/sso', 'sso-page'],
  [PERMISSIONS.ADMIN_AUDIT_VERIFY, '/admin/audit', 'audit-page'],
  [PERMISSIONS.ADMIN_QUOTAS_MANAGE, '/admin/quotas', 'quotas-page'],
  [PERMISSIONS.ADMIN_SECURITY_MANAGE, '/admin/detection', 'detection-page'],
];

function authorize(permissions: Permission[]) {
  server.use(
    http.get('/api/v1/auth/me', () =>
      HttpResponse.json({
        id: 'permission-user',
        username: 'permission-user',
        display_name: 'Permission User',
        role: 'admin',
        role_name: 'admin',
        permissions,
      })
    )
  );
}

describe('App exact permission routes and landing', () => {
  beforeEach(() => {
    queryClient.clear();
  });

  it.each(routeCases)('allows %s only with %s', async (path, permission, marker) => {
    authorize([permission]);
    window.history.replaceState({}, '', path);

    render(<App />);

    expect(await screen.findByText(marker)).toBeInTheDocument();
    expect(window.location.pathname).toBe(path);
  });

  it('replaces the legacy /ask entry with the guarded Workspace route', async () => {
    authorize([PERMISSIONS.QUERY_SUBMIT]);
    window.history.replaceState({}, '', '/ask');
    const historyLength = window.history.length;

    render(<App />);

    expect(await screen.findByText('workspace-page')).toBeInTheDocument();
    expect(screen.queryByText('ask-page')).not.toBeInTheDocument();
    expect(window.location.pathname).toBe('/');
    expect(window.history.length).toBe(historyLength);
  });

  it.each(routeCases)('denies %s when its exact permission is absent', async (path, permission, marker) => {
    const unrelatedPermission = permission === PERMISSIONS.QUERY_SUBMIT
      ? PERMISSIONS.QUERY_HISTORY_VIEW
      : PERMISSIONS.QUERY_SUBMIT;
    authorize([unrelatedPermission]);
    window.history.replaceState({}, '', path);

    render(<App />);

    expect(await screen.findByText('access-denied-page')).toBeInTheDocument();
    expect(screen.queryByText(marker)).not.toBeInTheDocument();
    expect(window.location.pathname).toBe('/access-denied');
  });

  it.each(landingCases)(
    'lands wildcard navigation for %s on %s',
    async (permission, path, marker) => {
      authorize([permission]);
      window.history.replaceState({}, '', '/unknown-location');

      render(<App />);

      expect(await screen.findByText(marker)).toBeInTheDocument();
      expect(window.location.pathname).toBe(path);
    }
  );

  it('sends a direct unauthorized URL to access denied instead of another privileged page', async () => {
    authorize([PERMISSIONS.QUERY_HISTORY_VIEW]);
    window.history.replaceState({}, '', '/admin/audit');

    render(<App />);

    expect(await screen.findByText('access-denied-page')).toBeInTheDocument();
    expect(screen.queryByText('audit-page')).not.toBeInTheDocument();
    expect(screen.queryByText('history-page')).not.toBeInTheDocument();
    expect(window.location.pathname).toBe('/access-denied');
  });

  it('mounts route-aware document titles in the application router', async () => {
    authorize([PERMISSIONS.QUERY_HISTORY_VIEW]);
    document.title = 'Unbranded';
    window.history.replaceState({}, '', '/history');

    render(<App />);

    expect(await screen.findByText('history-page')).toBeInTheDocument();
    expect(document.title).toBe('Query History | QueryCraft');
  });
});

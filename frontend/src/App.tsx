import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
  useNavigate,
} from 'react-router-dom';
import { QueryProvider } from './providers/QueryProvider';
import { useCurrentUser } from './hooks/useAuth';
import './i18n';
import './index.css';

import { SignInPage } from './pages/SignInPage';
import HistoryPage from './pages/HistoryPage';
import { WorkspacePage, type WorkspacePrefill } from './pages/WorkspacePage';
import { SettingsPage } from './pages/SettingsPage';
import { AdminConnectionsPage } from './pages/AdminConnectionsPage';
import { AdminSsoPage } from './pages/AdminSsoPage';
import { AdminRolesPage } from './pages/AdminRolesPage';
import { AdminAuditPage } from './pages/AdminAuditPage';
import { AdminQuotasPage } from './pages/AdminQuotasPage';
import { AdminDetectionPage } from './pages/AdminDetectionPage';
import { AccessDeniedPage } from './pages/AccessDeniedPage';
import { AppShell } from './components/shell/AppShell';
import { sessionAwareSignInPath } from './auth/sessionExpiry';

import { PermissionGuard } from './components/auth/PermissionGuard';
import { DocumentTitle } from './components/common/DocumentTitle';
import { RouteErrorBoundary } from './components/common/RouteErrorBoundary';
import { applyDocumentLanguage, normalizeAppLanguage } from './i18n/locale';
import {
  firstPermittedRoute,
  PROTECTED_ROUTE_CATALOG,
  type Permission,
  type ProtectedRoutePath,
} from './auth/permissions';

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { data: response, isLoading } = useCurrentUser();
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
      </div>
    );
  }
  if (!response?.data) {
    return <Navigate to={sessionAwareSignInPath()} replace />;
  }
  return <>{children}</>;
}

const protectedPageByPath: Record<Exclude<ProtectedRoutePath, '/'>, React.ReactNode> = {
  '/history': <HistoryPage />,
  '/settings': <SettingsPage />,
  '/admin/connections': <AdminConnectionsPage />,
  '/admin/roles': <AdminRolesPage />,
  '/admin/sso': <AdminSsoPage />,
  '/admin/audit': <AdminAuditPage />,
  '/admin/quotas': <AdminQuotasPage />,
  '/admin/detection': <AdminDetectionPage />,
};

function RootRedirect() {
  const { data: response, isLoading } = useCurrentUser();
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
      </div>
    );
  }
  const user = response?.data;
  if (user) {
    return <Navigate to={firstPermittedRoute(user) ?? '/access-denied'} replace />;
  }
  return <Navigate to={sessionAwareSignInPath()} replace />;
}

function ProtectedLayout({
  children,
  permission,
  locationKey,
}: {
  children: React.ReactNode;
  permission: Permission;
  locationKey?: string;
}) {
  return (
    <PermissionGuard permission={permission}>
      <AppShell>
        {/* Keyed by the route entry so deliberate navigation replaces a failed boundary. */}
        <RouteErrorBoundary key={locationKey}>{children}</RouteErrorBoundary>
      </AppShell>
    </PermissionGuard>
  );
}

function ApplicationRoutes({
  workspacePrefill,
  onWorkspacePrefillConsumed,
}: {
  workspacePrefill: WorkspacePrefill | null;
  onWorkspacePrefillConsumed: () => void;
}) {
  const location = useLocation();
  const authorizationState = location.state as { verifiedAuthorizationKey?: string } | null;
  const authorizationKey =
    authorizationState?.verifiedAuthorizationKey ?? `${location.key}:${location.pathname}`;
  return (
    <QueryProvider authorizationKey={authorizationKey}>
      <Routes>
          <Route path="/sign-in" element={<SignInPage />} />
          {PROTECTED_ROUTE_CATALOG.map(({ path, permission }) => (
            <Route
              key={path}
              path={path}
              element={
                <ProtectedLayout permission={permission} locationKey={location.key}>
                  {path === '/' ? (
                    <WorkspacePage
                      prefill={workspacePrefill}
                      onPrefillConsumed={onWorkspacePrefillConsumed}
                    />
                  ) : protectedPageByPath[path]}
                </ProtectedLayout>
              }
            />
          ))}
          <Route
            path="/access-denied"
            element={
              <AuthGuard>
                <AccessDeniedPage />
              </AuthGuard>
            }
          />
          <Route path="*" element={<RootRedirect />} />
      </Routes>
    </QueryProvider>
  );
}

function LegacyAskRedirect({
  onRedirect,
}: {
  onRedirect: (prefill: WorkspacePrefill) => void;
}) {
  const { search } = useLocation();
  const navigate = useNavigate();
  const { connectionId, question, workspaceSearch } = legacyAskHandoff(search);

  useEffect(() => {
    onRedirect({ question, connectionId });
    navigate({ pathname: '/', search: workspaceSearch }, { replace: true });
  }, [connectionId, navigate, onRedirect, question, workspaceSearch]);

  return null;
}

function legacyAskHandoff(search: string) {
  const legacyParams = new URLSearchParams(search);
  const workspaceParams = new URLSearchParams();
  for (const language of legacyParams.getAll('lng')) {
    workspaceParams.append('lng', language);
  }
  return {
    question: legacyParams.has('question') ? legacyParams.get('question') ?? '' : null,
    connectionId: legacyParams.has('connectionId')
      ? legacyParams.get('connectionId') ?? ''
      : null,
    workspaceSearch: workspaceParams.toString(),
  };
}

function ApplicationRouter() {
  const { pathname } = useLocation();
  const [workspacePrefill, setWorkspacePrefill] = useState<WorkspacePrefill | null>(null);
  const clearWorkspacePrefill = useCallback(() => setWorkspacePrefill(null), []);

  useEffect(() => {
    // Authentication/permission redirects must not retain a bookmark prefill in memory.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (pathname !== '/' && pathname !== '/ask') clearWorkspacePrefill();
  }, [clearWorkspacePrefill, pathname]);

  return pathname === '/ask' ? (
    <LegacyAskRedirect onRedirect={setWorkspacePrefill} />
  ) : (
    <ApplicationRoutes
      workspacePrefill={workspacePrefill}
      onWorkspacePrefillConsumed={clearWorkspacePrefill}
    />
  );
}

function App() {
  const { i18n } = useTranslation();

  useEffect(() => {
    // One central lang/dir sync point; variants normalize via the helper.
    applyDocumentLanguage(normalizeAppLanguage(i18n.resolvedLanguage ?? i18n.language) ?? 'en');
  }, [i18n.language, i18n.resolvedLanguage]);

  return (
    <BrowserRouter>
      <DocumentTitle />
      <ApplicationRouter />
    </BrowserRouter>
  );
}

export default App;

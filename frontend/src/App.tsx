import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { QueryProvider } from './providers/QueryProvider';
import { useCurrentUser } from './hooks/useAuth';
import './i18n';
import './index.css';

import { SignInPage } from './pages/SignInPage';
import { AskQuestionPage } from './pages/AskQuestionPage';
import HistoryPage from './pages/HistoryPage';
import { WorkspacePage } from './pages/WorkspacePage';
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

const protectedPageByPath: Record<ProtectedRoutePath, React.ReactNode> = {
  '/': <WorkspacePage />,
  '/ask': <AskQuestionPage />,
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
}: {
  children: React.ReactNode;
  permission: Permission;
}) {
  return (
    <PermissionGuard permission={permission}>
      <AppShell>{children}</AppShell>
    </PermissionGuard>
  );
}

function ApplicationRoutes() {
  const location = useLocation();
  return (
    <QueryProvider authorizationKey={`${location.key}:${location.pathname}`}>
      <Routes>
          <Route path="/sign-in" element={<SignInPage />} />
          {PROTECTED_ROUTE_CATALOG.map(({ path, permission }) => (
            <Route
              key={path}
              path={path}
              element={
                <ProtectedLayout permission={permission}>
                  {protectedPageByPath[path]}
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

function App() {
  const { i18n } = useTranslation();

  useEffect(() => {
    // One central lang/dir sync point; variants normalize via the helper.
    applyDocumentLanguage(normalizeAppLanguage(i18n.resolvedLanguage ?? i18n.language) ?? 'en');
  }, [i18n.language, i18n.resolvedLanguage]);

  return (
    <BrowserRouter>
      <ApplicationRoutes />
    </BrowserRouter>
  );
}

export default App;

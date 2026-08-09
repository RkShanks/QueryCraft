import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
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

import { PermissionGuard } from './components/auth/PermissionGuard';
import { firstPermittedRoute, PERMISSIONS, type Permission } from './auth/permissions';


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
    return <Navigate to="/sign-in" replace />;
  }
  return <>{children}</>;
}



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
  return <Navigate to="/sign-in" replace />;
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

function App() {
  const { i18n } = useTranslation();

  useEffect(() => {
    const dir = i18n.language === 'ar' ? 'rtl' : 'ltr';
    document.documentElement.dir = dir;
    document.documentElement.lang = i18n.language;
  }, [i18n.language]);

  return (
    <QueryProvider>

      <BrowserRouter>
        <Routes>
          <Route path="/sign-in" element={<SignInPage />} />
          <Route
            path="/"
            element={
              <ProtectedLayout permission={PERMISSIONS.QUERY_SUBMIT}>
                <WorkspacePage />
              </ProtectedLayout>
            }
          />
          <Route
            path="/ask"
            element={
              <ProtectedLayout permission={PERMISSIONS.QUERY_SUBMIT}>
                <AskQuestionPage />
              </ProtectedLayout>
            }
          />
          <Route
            path="/history"
            element={
              <ProtectedLayout permission={PERMISSIONS.QUERY_HISTORY_VIEW}>
                <HistoryPage />
              </ProtectedLayout>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedLayout permission={PERMISSIONS.ADMIN_CONNECTIONS_MANAGE}>
                <SettingsPage />
              </ProtectedLayout>
            }
          />
          <Route
            path="/admin/connections"
            element={
              <ProtectedLayout permission={PERMISSIONS.ADMIN_CONNECTIONS_MANAGE}>
                <AdminConnectionsPage />
              </ProtectedLayout>
            }
          />
          <Route
            path="/admin/sso"
            element={
              <ProtectedLayout permission={PERMISSIONS.ADMIN_SSO_MANAGE}>
                <AdminSsoPage />
              </ProtectedLayout>
            }
          />
          <Route
            path="/admin/roles"
            element={
              <ProtectedLayout permission={PERMISSIONS.ADMIN_ROLES_MANAGE}>
                <AdminRolesPage />
              </ProtectedLayout>
            }
          />
          <Route
            path="/admin/audit"
            element={
              <ProtectedLayout permission={PERMISSIONS.ADMIN_AUDIT_VERIFY}>
                <AdminAuditPage />
              </ProtectedLayout>
            }
          />
          <Route
            path="/admin/quotas"
            element={
              <ProtectedLayout permission={PERMISSIONS.ADMIN_QUOTAS_MANAGE}>
                <AdminQuotasPage />
              </ProtectedLayout>
            }
          />
          <Route
            path="/admin/detection"
            element={
              <ProtectedLayout permission={PERMISSIONS.ADMIN_SECURITY_MANAGE}>
                <AdminDetectionPage />
              </ProtectedLayout>
            }
          />
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
      </BrowserRouter>
    </QueryProvider>
  );
}

export default App;

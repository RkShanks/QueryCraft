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
import { AppShell } from './components/shell/AppShell';

import { PermissionGuard } from './components/auth/PermissionGuard';


function AuthGuard({ children }: { children: React.ReactNode }) {
  const { data: user, isLoading } = useCurrentUser();
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/sign-in" replace />;
  }
  return <>{children}</>;
}



function RootRedirect() {
  const { data: user, isLoading } = useCurrentUser();
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
      </div>
    );
  }
  if (user) {
    return <Navigate to="/" replace />;
  }
  return <Navigate to="/sign-in" replace />;
}

function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AppShell>{children}</AppShell>
    </AuthGuard>
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
              <AuthenticatedLayout>
                <WorkspacePage />
              </AuthenticatedLayout>
            }
          />
          <Route
            path="/ask"
            element={
              <AuthenticatedLayout>
                <AskQuestionPage />
              </AuthenticatedLayout>
            }
          />
          <Route
            path="/history"
            element={
              <AuthenticatedLayout>
                <HistoryPage />
              </AuthenticatedLayout>
            }
          />
          <Route
            path="/settings"
            element={
              <AuthenticatedLayout>
                <SettingsPage />
              </AuthenticatedLayout>
            }
          />
          <Route
            path="/admin/connections"
            element={
              <AuthenticatedLayout>
                <PermissionGuard permission="admin.connections.manage">
                  <AdminConnectionsPage />
                </PermissionGuard>
              </AuthenticatedLayout>
            }
          />
          <Route
            path="/admin/sso"
            element={
              <AuthenticatedLayout>
                <PermissionGuard permission="admin.sso.manage">
                  <AdminSsoPage />
                </PermissionGuard>
              </AuthenticatedLayout>
            }
          />
          <Route
            path="/admin/roles"
            element={
              <AuthenticatedLayout>
                <PermissionGuard permission="admin.roles.manage">
                  <AdminRolesPage />
                </PermissionGuard>
              </AuthenticatedLayout>
            }
          />
          <Route
            path="/admin/audit"
            element={
              <AuthenticatedLayout>
                <PermissionGuard permission="admin.audit.verify">
                  <AdminAuditPage />
                </PermissionGuard>
              </AuthenticatedLayout>
            }
          />
          <Route
            path="/admin/quotas"
            element={
              <AuthenticatedLayout>
                <PermissionGuard permission="admin.quotas.manage">
                  <AdminQuotasPage />
                </PermissionGuard>
              </AuthenticatedLayout>
            }
          />
          <Route
            path="/admin/detection"
            element={
              <AuthenticatedLayout>
                <PermissionGuard permission="admin.security.manage">
                  <AdminDetectionPage />
                </PermissionGuard>
              </AuthenticatedLayout>
            }
          />
          <Route path="*" element={<RootRedirect />} />


        </Routes>
      </BrowserRouter>
    </QueryProvider>
  );
}

export default App;

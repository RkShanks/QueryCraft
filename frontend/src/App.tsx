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
import { AppShell } from './components/shell/AppShell';


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

function PermissionGuard({ children, permission }: { children: React.ReactNode; permission: string }) {
  const { data: response, isLoading } = useCurrentUser();
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
      </div>
    );
  }
  const user = response?.data;
  if (!user) {
    return <Navigate to="/sign-in" replace />;
  }
  const hasPermission =
    user.role === 'admin' ||
    user.role_name === 'admin' ||
    user.permissions?.includes(permission);

  if (!hasPermission) {
    return <Navigate to="/" replace />;
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
          <Route path="*" element={<RootRedirect />} />

        </Routes>
      </BrowserRouter>
    </QueryProvider>
  );
}

export default App;

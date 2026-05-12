import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryProvider } from './providers/QueryProvider';
import { useCurrentUser } from './hooks/useAuth';
import './i18n';
import './index.css';

import { SignInPage } from './pages/SignInPage';
import { AskQuestionPage } from './pages/AskQuestionPage';
import HistoryPage from './pages/HistoryPage';
import { WorkspacePage } from './pages/WorkspacePage';
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
          <Route path="*" element={<RootRedirect />} />
        </Routes>
      </BrowserRouter>
    </QueryProvider>
  );
}

export default App;

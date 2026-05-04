import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryProvider } from './providers/QueryProvider';
import './i18n';
import './index.css';

// Lazy-loaded page stubs
import LoginPage from './pages/LoginPage.tsx';
import QueryPage from './pages/QueryPage.tsx';
import HistoryPage from './pages/HistoryPage.tsx';

function App() {
  return (
    <QueryProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/query" element={<QueryPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryProvider>
  );
}

export default App;

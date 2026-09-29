// App.tsx — six SentinelPay routes + session guard (Slice 4).
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import type { ReactElement } from 'react';
import TopBar from './components/TopBar';
import AuditPage from './pages/AuditPage';
import DashboardPage from './pages/DashboardPage';
import HistoryPage from './pages/HistoryPage';
import LoginPage from './pages/LoginPage';
import ResultPage from './pages/ResultPage';
import TransactionPage from './pages/TransactionPage';
import { SessionProvider, useSession } from './state/session';

function Guard({ children }: { children: ReactElement }) {
  const location = useLocation();
  const { user, loading } = useSession();
  if (loading) {
    return <div className="shell"><span className="spinner">Loading…</span></div>;
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}

export default function App() {
  return (
    <SessionProvider>
      <TopBar />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/transaction" element={<Guard><TransactionPage /></Guard>} />
        <Route path="/result/:id" element={<Guard><ResultPage /></Guard>} />
        <Route path="/dashboard" element={<Guard><DashboardPage /></Guard>} />
        <Route path="/history" element={<Guard><HistoryPage /></Guard>} />
        <Route path="/audit" element={<Guard><AuditPage /></Guard>} />
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="*" element={<div className="shell"><p>Not found. <a href="/transaction">Go to Transaction</a></p></div>} />
      </Routes>
    </SessionProvider>
  );
}

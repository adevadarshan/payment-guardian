// components/TopBar — shared header/nav mirroring the Flutter app bar.
import { NavLink, useNavigate } from 'react-router-dom';
import { useSession } from '../state/session';

export default function TopBar() {
  const navigate = useNavigate();
  const { signOut } = useSession();
  const logout = () => {
    void signOut().finally(() => navigate('/login'));
  };
  return (
    <header className="topbar">
      <strong>SentinelPay</strong>
      <span className="muted">Fraud Detection (web shell)</span>
      <nav>
        <NavLink to="/transaction" className={({ isActive }) => (isActive ? 'active' : '')}>Transaction</NavLink>
        <NavLink to="/dashboard" className={({ isActive }) => (isActive ? 'active' : '')}>Dashboard</NavLink>
        <NavLink to="/history" className={({ isActive }) => (isActive ? 'active' : '')}>History</NavLink>
        <NavLink to="/audit" className={({ isActive }) => (isActive ? 'active' : '')}>Audit</NavLink>
        <button className="secondary" onClick={logout} style={{ padding: '4px 10px' }}>Logout</button>
      </nav>
    </header>
  );
}

// pages/LoginPage — real login against the API; look unchanged (Slice 4).
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client';
import { SentinelButton, SentinelCard } from '../components/widgets';
import { useSession } from '../state/session';

export default function LoginPage() {
  const navigate = useNavigate();
  const { signIn } = useSession();
  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await signIn(userId.trim(), password);
      navigate('/transaction');
    } catch (err) {
      if (err instanceof ApiError && err.kind === 'unauthorized') {
        setError('Invalid email or password.');
      } else if (err instanceof ApiError && err.kind === 'rate_limited') {
        setError(`Too many attempts. ${err.message}`);
      } else {
        setError(err instanceof ApiError ? err.message : 'Sign-in failed.');
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="shell" style={{ maxWidth: 520 }}>
      <h1>SentinelPay</h1>
      <p className="muted">Fraud Detection System</p>
      <SentinelCard>
        <h2>Welcome back</h2>
        <p className="muted">Sign in to your SentinelPay account</p>
        <form onSubmit={submit}>
          <label htmlFor="userid">User ID</label>
          <input id="userid" value={userId} onChange={(e) => setUserId(e.target.value)} autoComplete="username" />
          <label htmlFor="password">Password</label>
          <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          {error && (
            <div className="alert alert-danger" role="alert">{error}</div>
          )}
          <div style={{ marginTop: 16 }}>
            <SentinelButton type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign In'}</SentinelButton>
          </div>
        </form>
      </SentinelCard>
      <div className="alert alert-info">Use the demo account seeded by your administrator.</div>
    </div>
  );
}

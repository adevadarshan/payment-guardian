// session tests (Slice 4): login/logout/guard/401/expired-session states.
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import LoginPage from '../pages/LoginPage';
import { SessionProvider, useSession } from './session';

function mockApi(handler: (url: string, init?: RequestInit) => { ok: boolean; status?: number; body: unknown }) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const r = handler(String(input), init);
    return { ok: r.ok, status: r.status ?? (r.ok ? 200 : 500), json: async () => r.body } as Response;
  });
}

function renderLogin() {
  render(
    <MemoryRouter initialEntries={['/login']}>
      <SessionProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/transaction" element={<div>transaction-page</div>} />
        </Routes>
      </SessionProvider>
    </MemoryRouter>,
  );
}

function Probe() {
  const { user, loading } = useSession();
  if (loading) return <div>loading</div>;
  return <div>{user ? `user:${user.email}` : 'anonymous'}</div>;
}

describe('session', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('successful login stores the session and navigates', async () => {
    const user = userEvent.setup();
    mockApi((url) => {
      if (url.endsWith('/auth/login')) {
        return { ok: true, body: { access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 3600 } };
      }
      if (url.endsWith('/auth/me')) {
        return { ok: true, body: { id: '1', email: 'demo@vhs02.local', display_name: 'Demo', is_demo: true } };
      }
      return { ok: false, status: 404, body: {} };
    });
    renderLogin();
    await user.type(screen.getByLabelText(/user id/i), 'demo@vhs02.local');
    await user.type(screen.getByLabelText(/password/i), 'demo1234');
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    await waitFor(() => expect(screen.getByText('transaction-page')).toBeInTheDocument());
  });

  it('bad credentials show an error and stay on login', async () => {
    const user = userEvent.setup();
    mockApi(() => ({ ok: false, status: 401, body: { error: { code: 'unauthorized', message: 'Invalid email or password.' } } }));
    renderLogin();
    await user.type(screen.getByLabelText(/user id/i), 'x@y.zz');
    await user.type(screen.getByLabelText(/password/i), 'wrong');
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    await waitFor(() => expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument());
  });

  it('rate-limited login shows the wait message', async () => {
    const user = userEvent.setup();
    mockApi(() => ({ ok: false, status: 429, body: { error: { code: 'rate_limited', message: 'Slow down.', details: { retry_after: 30 } } } }));
    renderLogin();
    await user.type(screen.getByLabelText(/user id/i), 'x@y.zz');
    await user.type(screen.getByLabelText(/password/i), 'wrong');
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    await waitFor(() => expect(screen.getByText(/too many attempts/i)).toBeInTheDocument());
  });

  it('expired session resolves to anonymous', async () => {
    mockApi(() => ({ ok: false, status: 401, body: { error: { code: 'unauthorized', message: 'Nope' } } }));
    render(
      <MemoryRouter>
        <SessionProvider>
          <Probe />
        </SessionProvider>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('anonymous')).toBeInTheDocument());
  });
});

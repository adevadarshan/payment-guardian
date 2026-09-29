// api/auth.ts — typed auth calls + token plumbing (Slice 4).
// Tokens live in memory via the session context; persistence choice (if any)
// stays inside state/session.tsx. No credentials are ever logged.
import { apiGet, apiPost, setAuthHeaderProvider, setUnauthorizedHandler } from './client';

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface Me {
  id: string;
  email: string;
  display_name: string | null;
  is_demo: boolean;
}

let accessToken: string | null = null;
let refreshToken: string | null = null;
let refreshing: Promise<TokenPair | null> | null = null;
let expiredCallback: (() => void) | null = null;

export function setTokens(pair: TokenPair | null): void {
  accessToken = pair?.access_token || null;
  refreshToken = pair?.refresh_token || null;
  setAuthHeaderProvider(() => (accessToken ? `Bearer ${accessToken}` : null));
}

export function clearTokens(): void {
  setTokens(null);
}

export function setSessionExpiredHandler(fn: () => void): void {
  expiredCallback = fn;
}

async function doRefresh(): Promise<TokenPair | null> {
  if (!refreshToken) return null;
  if (!refreshing) {
    refreshing = apiPost<TokenPair>('/auth/refresh', { refresh_token: refreshToken })
      .then((pair) => {
        setTokens(pair);
        return pair;
      })
      .catch(() => null)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

/** Called by client.ts on 401: refresh once, then signal logout if still dead. */
export async function handleUnauthorized(): Promise<boolean> {
  const pair = await doRefresh();
  if (pair) return true;
  clearTokens();
  if (expiredCallback) expiredCallback();
  return false;
}

setUnauthorizedHandler(handleUnauthorized);

export const login = (email: string, password: string) =>
  apiPost<TokenPair>('/auth/login', { email, password });

export const logout = () => apiPost<{ status: string }>('/auth/logout', {});

export const fetchMe = () => apiGet<Me>('/auth/me');

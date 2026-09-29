// api/client.ts — fetch wrapper with a typed ApiError union (Slice 1).
// Base URL comes from VITE_API_BASE_URL only. No hostnames in source.

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '/api';

export type ApiErrorKind = 'network' | 'timeout' | 'validation' | 'unauthorized' | 'rate_limited' | 'server';

export class ApiError extends Error {
  kind: ApiErrorKind;
  status?: number;
  details?: unknown;
  constructor(kind: ApiErrorKind, message: string, status?: number, details?: unknown) {
    super(message);
    this.kind = kind;
    this.status = status;
    this.details = details;
  }
}

type HeaderProvider = () => string | null;
let authHeaderProvider: HeaderProvider | null = null;
let unauthorizedHandler: (() => Promise<boolean>) | null = null;
let refreshAttempted = false;

/** Registered by api/auth.ts. Keeps token plumbing out of every call site. */
export function setAuthHeaderProvider(fn: HeaderProvider | null): void {
  authHeaderProvider = fn;
}

/** Registered by api/auth.ts: refresh once per 401, then give up. */
export function setUnauthorizedHandler(fn: (() => Promise<boolean>) | null): void {
  unauthorizedHandler = fn;
  refreshAttempted = false;
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 15000): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  const authHeader = authHeaderProvider ? authHeaderProvider() : null;
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(authHeader ? { Authorization: authHeader } : {}),
        ...(init?.headers || {}),
      },
    });
  } catch (e) {
    clearTimeout(timer);
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ApiError('timeout', 'Request timed out. Is the backend running?');
    }
    throw new ApiError('network', 'Cannot reach the server. Check VITE_API_BASE_URL.');
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 401 && unauthorizedHandler && !refreshAttempted) {
    refreshAttempted = true;
    try {
      const recovered = await unauthorizedHandler();
      if (recovered) {
        refreshAttempted = false;
        return request<T>(path, init, timeoutMs);
      }
    } finally {
      refreshAttempted = false;
    }
  }
  if (!res.ok) {
    let body: { error?: { code?: string; message?: string; details?: unknown } } = {};
    try {
      body = (await res.json()) as typeof body;
    } catch {
      /* non-JSON error body */
    }
    const code = body.error?.code;
    const message = body.error?.message || `Server error (${res.status})`;
    if (res.status === 422 || code === 'validation_error') {
      throw new ApiError('validation', message, res.status, body.error?.details);
    }
    if (res.status === 401) throw new ApiError('unauthorized', message, res.status);
    if (res.status === 429) throw new ApiError('rate_limited', message, res.status);
    throw new ApiError('server', message, res.status);
  }
  return (await res.json()) as T;
}

export const apiGet = <T>(path: string) => request<T>(path, { method: 'GET' });
export const apiPost = <T>(path: string, body: unknown) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body) });

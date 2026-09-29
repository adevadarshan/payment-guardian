// lib/balance.ts — demo/local session balance for the Make Payment flow (Slice 2).
// Explicitly NOT a server-side payment: a localStorage-backed demo balance.
// Real ledger behaviour, if ever needed, belongs server-side (out of scope).
export const BALANCE_KEY = 'vhs02-balance';

export function readBalance(): string {
  try {
    return localStorage.getItem(BALANCE_KEY) || '';
  } catch {
    return '';
  }
}

export function writeBalance(value: string): void {
  try {
    localStorage.setItem(BALANCE_KEY, value);
  } catch {
    /* storage unavailable */
  }
}

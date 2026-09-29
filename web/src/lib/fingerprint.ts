// lib/fingerprint.ts — weak browser context signal, clearly labelled (Slice 1).
// Never a device identity; only echoed for transparency on the result page.
export interface BrowserContext {
  installId: string;
  platform: string;
  language: string;
  timezone: string;
}

const KEY = 'vhs02-install-id';

export function getBrowserContext(): BrowserContext {
  let installId = '';
  try {
    installId = localStorage.getItem(KEY) || '';
    if (!installId) {
      installId = `WEB_${Math.random().toString(36).slice(2, 10).toUpperCase()}`;
      localStorage.setItem(KEY, installId);
    }
  } catch {
    installId = 'WEB_UNKNOWN';
  }
  return {
    installId,
    platform: typeof navigator !== 'undefined' ? navigator.platform || 'unknown' : 'unknown',
    language: typeof navigator !== 'undefined' ? navigator.language || 'unknown' : 'unknown',
    timezone: (() => {
      try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || 'unknown';
      } catch {
        return 'unknown';
      }
    })(),
  };
}

// lib/gates.ts — client-side pre-checks ported from SentinelPay behaviour (Slice 1).
// UX only. The server repeats every check it depends on.

const UPI_RE = /^[A-Za-z0-9.\-_]{2,256}@[A-Za-z][A-Za-z0-9]{1,64}$/;
const MAX_PER_MINUTE = 5;
const stamps: number[] = [];

export function checkRateLimit(): { allowed: boolean; retryAfterSec: number } {
  const now = Date.now();
  while (stamps.length && now - stamps[0] > 60_000) stamps.shift();
  if (stamps.length >= MAX_PER_MINUTE) {
    return { allowed: false, retryAfterSec: Math.ceil((60_000 - (now - stamps[0])) / 1000) };
  }
  stamps.push(now);
  return { allowed: true, retryAfterSec: 0 };
}

export function validateUpi(payeeId: string): string | null {
  if (!UPI_RE.test(payeeId.trim())) return 'Invalid UPI ID format. Expected: name@bank';
  return null;
}

export function validateAmount(amountStr: string): { amount?: number; error?: string } {
  const amount = Number(amountStr.trim().replace(/,/g, ''));
  if (!Number.isFinite(amount) || amount <= 0) return { error: 'Amount must be a positive number.' };
  if (amount > 200000) return { error: 'Amount exceeds the UPI transaction limit of Rs.2,00,000.' };
  return { amount };
}

export function sanitiseNote(note: string): string {
  return note
    .replace(/<[^>]*>/g, '')
    .replace(/[<>&"']/g, '')
    .replace(/[\u0000-\u001F\u007F]/g, '')
    .slice(0, 280);
}

// Adversarial probe pattern: amounts stepping by small uniform increments.
const recent: number[] = [];
export function checkProbePattern(amount: number): string | null {
  recent.push(amount);
  if (recent.length > 5) recent.shift();
  if (recent.length < 3) return null;
  const diffs = recent.slice(1).map((v, i) => Math.abs(v - recent[i]));
  const avg = diffs.reduce((a, b) => a + b, 0) / diffs.length;
  const max = Math.max(...diffs);
  if (avg > 0 && max < avg * 1.2 && avg < 200) {
    return 'Systematic amount stepping detected. Multiple transactions with incrementally similar amounts.';
  }
  for (const t of [1000, 2000, 5000, 10000, 20000, 50000]) {
    if (amount > t * 0.95 && amount < t) {
      return `Amount Rs.${amount} sits just below the Rs.${t} threshold. Flagged for review.`;
    }
  }
  return null;
}

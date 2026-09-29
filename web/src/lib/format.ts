// lib/format.ts
export const inr = (n: number) =>
  `Rs.${Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;

export const levelClass = (level: string) =>
  level === 'SAFE' ? 'badge-safe' : level === 'MEDIUM' ? 'badge-medium' : 'badge-high';

export const shortHash = (h: string) => (h.length > 12 ? `${h.slice(0, 12)}...` : h);

// components/RiskIndicator.tsx — static SVG arc gauge (Slice 2).
// Same visual role as the SentinelPay RiskIndicator. No animation library.
import { levelClass } from '../lib/format';

const LEVEL_COLOR: Record<string, string> = {
  SAFE: 'var(--safe)',
  MEDIUM: 'var(--suspicious)',
  HIGH: 'var(--danger)',
};

export default function RiskIndicator({ score, level, size = 180 }: { score: number; level: string; size?: number }) {
  const clamped = Math.max(0, Math.min(100, score));
  const r = 70;
  const circ = Math.PI * r; // half-circle arc length
  const color = LEVEL_COLOR[level] || 'var(--text-secondary)';
  return (
    <div style={{ textAlign: 'center' }} role="img" aria-label={`Risk score ${clamped} out of 100, level ${level}`}>
      <svg width={size} height={size * 0.62} viewBox="0 0 160 100">
        <path d="M 10 90 A 70 70 0 0 1 150 90" fill="none" stroke="var(--bg3)" strokeWidth="14" strokeLinecap="round" />
        <path
          d="M 10 90 A 70 70 0 0 1 150 90"
          fill="none"
          stroke={color}
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray={`${(clamped / 100) * circ} ${circ}`}
        />
        <text x="80" y="72" textAnchor="middle" fill="var(--text-primary)" fontSize="30" fontWeight="800">
          {clamped}
        </text>
        <text x="80" y="88" textAnchor="middle" fill="var(--text-muted)" fontSize="11">
          / 100
        </text>
      </svg>
      <div style={{ marginTop: 4 }}>
        <span className={`badge ${levelClass(level)}`}>{level.replace('_', ' ')}</span>
      </div>
    </div>
  );
}

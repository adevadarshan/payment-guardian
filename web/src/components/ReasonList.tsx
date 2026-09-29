// components/ReasonList.tsx — ordered reasons (Slice 2). Copy comes from the API.
import type { Reason } from '../api/types';

const IMPACT_TONE: Record<string, string> = {
  high: 'var(--danger)',
  medium: 'var(--suspicious)',
  low: 'var(--text-secondary)',
  informational: 'var(--teal)',
};

export default function ReasonList({ reasons }: { reasons: Reason[] }) {
  if (!reasons.length) {
    return <p className="muted">No specific risk factors — nothing stood out in this check.</p>;
  }
  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {reasons.map((r) => (
        <li key={r.code} style={{ borderLeft: `3px solid ${IMPACT_TONE[r.impact] || 'var(--text-secondary)'}`, padding: '6px 0 6px 12px', marginBottom: 10 }}>
          <strong>{r.title}</strong>
          <div className="muted">{r.observation}</div>
          <div className="mono muted">{r.code} · {r.impact} impact</div>
        </li>
      ))}
    </ul>
  );
}

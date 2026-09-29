// components/BreachDialog.tsx — non-dismissible chain-breach modal (Slice 2).
import { Link } from 'react-router-dom';

export default function BreachDialog({ brokenAtId, reason }: { brokenAtId?: number; reason?: string }) {
  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-label="Audit chain breach"
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50,
      }}
    >
      <div className="card" style={{ maxWidth: 480, borderColor: 'var(--danger)' }}>
        <h2 style={{ color: 'var(--danger)' }}>Audit chain breach detected</h2>
        <p>
          {brokenAtId !== undefined ? `Entry ${brokenAtId} failed verification. ` : ''}
          {reason || 'The audit log was modified after it was written.'}
        </p>
        <Link className="btn" to="/audit">View Audit Log</Link>
      </div>
    </div>
  );
}

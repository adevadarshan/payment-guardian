// pages/AuditPage — server chain list + verify + JSON export (Slice 2).
// List refreshes every 10 seconds; verification stays manual.
import { useEffect, useState } from 'react';
import { fetchAudit, verifyChain } from '../api/analyze';
import { ApiError } from '../api/client';
import type { AuditEntry, ChainVerify } from '../api/types';
import { SectionHeader, SentinelButton, SentinelCard } from '../components/widgets';
import { shortHash } from '../lib/format';

const EVENT_LABELS: Record<string, string> = {
  SCAN_SUBMITTED: 'Scan submitted',
  QR_SEEN: 'QR first seen',
  RATE_LIMITED: 'Rate limited',
  TRANSACTION_SUBMITTED: 'Transaction submitted',
  RISK_RESULT_RECEIVED: 'Risk result received',
  SECURITY_EVENT: 'Security event',
  LOGIN: 'Login',
  LOGOUT: 'Logout',
};

export function eventLabel(eventType: string): string {
  return EVENT_LABELS[eventType] || eventType;
}

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [status, setStatus] = useState<ChainVerify | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = () => {
    fetchAudit(200)
      .then(setEntries)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load audit log.'));
  };

  useEffect(() => {
    load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, []);

  const verify = async () => {
    setBusy(true);
    try {
      setStatus(await verifyChain());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Verification failed.');
    } finally {
      setBusy(false);
    }
  };

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(entries, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'audit-log.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="shell">
      <SectionHeader title="Audit Log" trailing={<SentinelButton secondary onClick={exportJson}>Export JSON</SentinelButton>} />
      {error && (
        <div className="alert alert-danger" role="alert">{error}</div>
      )}
      <SentinelCard>
        <div className="row" style={{ alignItems: 'center' }}>
          <SentinelButton onClick={verify} disabled={busy}>
            {busy ? 'Verifying…' : 'Verify Chain Integrity'}
          </SentinelButton>
          {status && (
            status.valid ? (
              <span role="status">Chain valid — {status.entry_count} entries</span>
            ) : (
              <span role="alert" style={{ color: 'var(--danger)' }}>
                Chain broken at entry {status.broken_at_id}: {status.reason}
              </span>
            )
          )}
        </div>
      </SentinelCard>
      {entries.map((e) => (
        <SentinelCard key={e.id}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <strong>#{e.id} {eventLabel(e.event_type)}</strong>
            <span className="muted">{new Date(e.created_at).toLocaleString()}</span>
          </div>
          <div className="mono">entity {e.entity_type}/{e.entity_id.slice(0, 8)}</div>
          <div className="mono muted">prev {shortHash(e.previous_hash)} → {shortHash(e.entry_hash)}</div>
        </SentinelCard>
      ))}
      {entries.length === 0 && (
        <SentinelCard><p className="muted">No audit entries yet.</p></SentinelCard>
      )}
    </div>
  );
}

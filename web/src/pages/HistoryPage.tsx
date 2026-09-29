// pages/HistoryPage — server-side level filters (Slice 2). No Clear action:
// with DB-backed history there is no safe server-side equivalent and the
// audit log must stay append-only.
import { useCallback, useEffect, useState } from 'react';
import { fetchScans } from '../api/analyze';
import { ApiError } from '../api/client';
import type { ScanSummary } from '../api/types';
import { SectionHeader, SentinelCard, TransactionCard } from '../components/widgets';

const LEVEL_FILTERS = [
  { label: 'All', level: undefined },
  { label: 'Safe', level: 'SAFE' },
  { label: 'Suspicious', level: 'MEDIUM' },
  { label: 'High Risk', level: 'HIGH' },
] as const;

const TYPE_FILTERS = [
  { label: 'All types', type: undefined },
  { label: 'Payment', type: 'payment' },
  { label: 'Message', type: 'message' },
  { label: 'Link', type: 'url' },
  { label: 'QR', type: 'qr' },
] as const;

type LevelLabel = (typeof LEVEL_FILTERS)[number]['label'];
type TypeLabel = (typeof TYPE_FILTERS)[number]['label'];

export default function HistoryPage() {
  const [scans, setScans] = useState<ScanSummary[]>([]);
  const [level, setLevel] = useState<LevelLabel>('All');
  const [scanType, setScanType] = useState<TypeLabel>('All types');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback((levelLabel: LevelLabel, typeLabel: TypeLabel) => {
    setLoading(true);
    setError('');
    const levelParam = LEVEL_FILTERS.find((f) => f.label === levelLabel)?.level;
    const typeParam = TYPE_FILTERS.find((f) => f.label === typeLabel)?.type;
    fetchScans(50, levelParam, typeParam)
      .then(setScans)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load history.'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load('All', 'All types');
  }, [load]);

  const pickLevel = (label: LevelLabel) => {
    // Toggle: clicking the active chip returns to All (SentinelPay behaviour).
    const next = label === level ? 'All' : label;
    setLevel(next);
    load(next, scanType);
  };

  const pickType = (label: TypeLabel) => {
    setScanType(label);
    load(level, label);
  };

  return (
    <div className="shell">
      <SectionHeader title="Transaction History" />
      <div className="chips" role="group" aria-label="Filter by risk level">
        {LEVEL_FILTERS.map((f) => (
          <button key={f.label} className={level === f.label ? '' : 'secondary'} onClick={() => pickLevel(f.label)}>
            {f.label}
          </button>
        ))}
      </div>
      <div className="chips" role="group" aria-label="Filter by scan type">
        {TYPE_FILTERS.map((f) => (
          <button key={f.label} className={scanType === f.label ? '' : 'secondary'} onClick={() => pickType(f.label)}>
            {f.label}
          </button>
        ))}
      </div>
      <p className="muted">{scans.length} transactions</p>
      {loading && <span className="spinner">Loading history…</span>}
      {error && (
        <div className="alert alert-danger" role="alert">{error}</div>
      )}
      {!loading && !error && scans.length === 0 && (
        <SentinelCard><p className="muted">No transactions found.</p></SentinelCard>
      )}
      {scans.map((s) => (
        <TransactionCard key={s.scan_id} scan={s} />
      ))}
    </div>
  );
}

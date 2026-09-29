// pages/DashboardPage — stats API + Recharts pie/histogram (Slice 2).
// Section order mirrors SentinelPay: summary, fraud rate, pie, histogram,
// active alerts, suspicious activity, live feed.
import { useEffect, useState } from 'react';
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { fetchScans, fetchStats } from '../api/analyze';
import { ApiError } from '../api/client';
import type { ScanSummary, Stats } from '../api/types';
import { AlertBanner, SectionHeader, SentinelCard, StatsTile, TransactionCard } from '../components/widgets';

const BUCKET_COLORS = ['var(--safe)', 'var(--safe)', 'var(--suspicious)', 'var(--suspicious)', 'var(--danger)'];

function bucketIndex(score: number): number {
  return Math.max(0, Math.min(4, Math.floor(score / 20)));
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [scans, setScans] = useState<ScanSummary[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchStats(), fetchScans(50)])
      .then(([s, list]) => {
        setStats(s);
        setScans(list);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load dashboard.'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="shell"><span className="spinner">Loading dashboard…</span></div>;
  if (error) return <div className="shell"><div className="alert alert-danger" role="alert">{error}</div></div>;
  if (!stats) return <div className="shell"><p className="muted">No data.</p></div>;

  const fraudPct = (stats.fraud_rate * 100).toFixed(1);
  const pieData = [
    { name: 'Safe', value: stats.safe, fill: 'var(--safe)' },
    { name: 'Suspicious', value: stats.medium, fill: 'var(--suspicious)' },
    { name: 'High Risk', value: stats.high, fill: 'var(--danger)' },
  ].filter((d) => d.value > 0);
  const buckets = [0, 0, 0, 0, 0];
  for (const s of scans) buckets[bucketIndex(s.risk_score)] += 1;
  const bucketData = buckets.map((count, i) => ({
    bucket: `${i * 20}–${i * 20 + 20}`,
    count,
    fill: BUCKET_COLORS[i],
  }));
  const highAlerts = scans.filter((s) => s.risk_level === 'HIGH').slice(0, 3);
  const suspicious = scans.filter((s) => s.risk_level === 'MEDIUM').slice(0, 2);
  const byType = (['payment', 'message', 'url', 'qr'] as const).map((t) => ({
    type: t,
    count: scans.filter((s) => s.analysis_type === t).length,
  }));

  return (
    <div className="shell">
      <SectionHeader title="Fraud Dashboard" />
      <SectionHeader title="SUMMARY" />
      <div className="grid2">
        <StatsTile label="Total Transactions" value={String(stats.total)} />
        <StatsTile label="Fraud Detected" value={String(stats.high)} tone="var(--danger)" />
        <StatsTile label="Suspicious" value={String(stats.medium)} tone="var(--suspicious)" />
        <StatsTile label="Safe" value={String(stats.safe)} tone="var(--safe)" />
      </div>
      <div style={{ marginTop: 12 }}>
        <StatsTile label="Fraud rate" value={`${fraudPct}%`} tone={stats.fraud_rate > 0.2 ? 'var(--danger)' : undefined} />
      </div>

      <SectionHeader title="BY TYPE" />
      <div className="grid2">
        {byType.map((b) => (
          <StatsTile key={b.type} label={b.type} value={String(b.count)} />
        ))}
      </div>

      <SectionHeader title="RISK DISTRIBUTION" />
      <SentinelCard>
        {stats.total === 0 ? (
          <p className="muted" style={{ textAlign: 'center' }}>No data</p>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={40} outerRadius={70}>
                  {pieData.map((entry) => (
                    <Cell key={entry.name} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
            <div className="row" style={{ justifyContent: 'center' }}>
              <span><span className="chain-dot" style={{ background: 'var(--safe)' }} /> Safe</span>
              <span><span className="chain-dot" style={{ background: 'var(--suspicious)' }} /> Suspicious</span>
              <span><span className="chain-dot" style={{ background: 'var(--danger)' }} /> High Risk</span>
            </div>
          </>
        )}
      </SentinelCard>

      <SectionHeader title="RISK SCORE HISTOGRAM" />
      <SentinelCard>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={bucketData}>
            <XAxis dataKey="bucket" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
            <YAxis allowDecimals={false} tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="count">
              {bucketData.map((b) => (
                <Cell key={b.bucket} fill={b.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </SentinelCard>

      {highAlerts.length > 0 && (
        <>
          <SectionHeader title="ACTIVE ALERTS" />
          {highAlerts.map((s) => (
            <AlertBanner key={s.scan_id} kind="danger" title={`HIGH RISK — ${s.scan_id.slice(0, 8)}`} subtitle={`${s.label} · Score ${s.risk_score}/100`} />
          ))}
        </>
      )}
      {suspicious.length > 0 && (
        <>
          <SectionHeader title="SUSPICIOUS ACTIVITY" />
          {suspicious.map((s) => (
            <AlertBanner key={s.scan_id} kind="warn" title={`Suspicious — ${s.scan_id.slice(0, 8)}`} subtitle={`${s.label} · Score ${s.risk_score}/100`} />
          ))}
        </>
      )}

      <SectionHeader title="LIVE TRANSACTION FEED" />
      {scans.length === 0 && (
        <SentinelCard><p className="muted">No transactions yet.</p></SentinelCard>
      )}
      {scans.slice(0, 20).map((s) => (
        <TransactionCard key={s.scan_id} scan={s} />
      ))}
    </div>
  );
}

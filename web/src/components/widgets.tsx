// components/ — 1:1 port of sentinel_widgets.dart roles (Slice 1, static, no polish).
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { levelClass } from '../lib/format';import type { ScanSummary } from '../api/types';

export function SentinelCard({ children }: { children: ReactNode }) {
  return <div className="card">{children}</div>;
}

export function SectionHeader({ title, trailing }: { title: string; trailing?: ReactNode }) {
  return (
    <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
      <h3 className="muted" style={{ margin: '8px 0' }}>{title}</h3>
      {trailing}
    </div>
  );
}

export function SentinelButton({
  children, onClick, disabled, secondary, type,
}: {
  children: ReactNode; onClick?: () => void; disabled?: boolean; secondary?: boolean; type?: 'button' | 'submit';
}) {
  return (
    <button type={type || 'button'} onClick={onClick} disabled={disabled} className={secondary ? 'secondary' : ''}>
      {children}
    </button>
  );
}

export function RiskBadge({ level }: { level: string }) {
  return <span className={`badge ${levelClass(level)}`}>{level.replace('_', ' ')}</span>;
}

export function AlertBanner({ kind, title, subtitle }: { kind: 'danger' | 'warn' | 'info'; title: string; subtitle?: string }) {
  return (
    <div className={`alert alert-${kind}`}>
      <strong>{title}</strong>
      {subtitle && <div>{subtitle}</div>}
    </div>
  );
}

export function StatsTile({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="card" style={{ margin: 0 }}>
      <div className="muted" style={{ fontSize: 12 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 800, color: tone || 'var(--text-primary)' }}>{value}</div>
    </div>
  );
}

export function TransactionCard({ scan }: { scan: ScanSummary }) {
  return (
    <div className="card" style={{ marginBottom: 10 }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <span className="mono">{scan.scan_id.slice(0, 8)}</span>
        <RiskBadge level={scan.risk_level} />
      </div>
      <div style={{ marginTop: 6 }}>{scan.label}</div>
      <div className="muted" style={{ fontSize: 12 }}>
        Score {scan.risk_score}/100 · {new Date(scan.created_at).toLocaleString()}
      </div>
      <div style={{ marginTop: 8 }}>
        <Link to={`/result/${scan.scan_id}`}>Open result</Link>
      </div>
    </div>
  );
}

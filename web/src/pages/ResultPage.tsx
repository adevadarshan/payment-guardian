// pages/ResultPage — real verdict: gauge, reasons, action, summary, Make Payment (Slice 2).
// Make Payment is explicitly demo/local behaviour: it deducts from a
// localStorage session balance (vhs02-balance), never a server-side payment.
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { fetchScan } from '../api/analyze';
import { ApiError } from '../api/client';
import type { AnalysisResult } from '../api/types';
import ConfirmDialog from '../components/ConfirmDialog';
import EvidencePanel from '../components/EvidencePanel';
import ReasonList from '../components/ReasonList';
import RiskIndicator from '../components/RiskIndicator';
import SafeActionCard from '../components/SafeActionCard';
import SeenStatusBadge from '../components/SeenStatusBadge';
import AdvisoryNote from '../components/AdvisoryNote';
import { AlertBanner, RiskBadge, SectionHeader, SentinelButton, SentinelCard } from '../components/widgets';
import { getBrowserContext } from '../lib/fingerprint';
import { inr } from '../lib/format';
import { readBalance, writeBalance } from '../lib/balance';
export default function ResultPage() {
  const { id } = useParams();
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [paid, setPaid] = useState<string | null>(null);
  const ctx = getBrowserContext();

  useEffect(() => {
    if (!id) return;
    fetchScan(id)
      .then((r) => {
        setResult(r);
        // Seed the demo balance from the analysed sender_balance on first view.
        if (readBalance() === '' && r.payment_summary) {
          writeBalance(String(r.payment_summary.sender_balance));
        }
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load result.'));
  }, [id]);

  const needsConfirm = result && result.risk_level !== 'SAFE';

  const doPay = () => {
    if (!result?.payment_summary) return;
    const amount = result.payment_summary.amount;
    let current = Number(readBalance());
    if (!Number.isFinite(current)) current = result.payment_summary.sender_balance;
    const next = current - amount;
    writeBalance(String(next));
    setPaid(`${inr(amount)} sent. New balance: ${inr(next)}`);
    setConfirming(false);
  };

  if (error) return <div className="shell"><div className="alert alert-danger" role="alert">{error}</div></div>;
  if (!result) return <div className="shell"><span className="spinner">Loading result…</span></div>;

  return (
    <div className="shell">
      <SectionHeader title="Risk Analysis" trailing={<RiskBadge level={result.risk_level} />} />
      <SentinelCard>
        <RiskIndicator score={result.risk_score} level={result.risk_level} size={180} />
      </SentinelCard>
      <SentinelCard>
        <h3>Why this score</h3>
        <ReasonList reasons={result.reasons} />
      </SentinelCard>
      <SentinelCard>
        <h3>Recommended action</h3>
        <SafeActionCard headline={result.recommended_action.headline} steps={result.recommended_action.steps} />
      </SentinelCard>
      <SentinelCard>
        <EvidencePanel evidence={result.evidence} />
      </SentinelCard>
      {result.analysis_type === 'qr' && <SeenStatusBadge seen={result.seen} />}
      <p className="muted">
        Model: {result.model.backend === 'none' ? 'off' : result.model.version || result.model.backend}
        {' · '}Advisory: {result.advisory.status === 'ok' ? 'available' : result.advisory.status}
      </p>
      {result.advisory.status === 'ok' && result.advisory.text && (
        <AdvisoryNote text={result.advisory.text} provider={result.advisory.provider} />
      )}
      <SentinelCard>
        <h3>Transaction summary</h3>
        <div className="mono">Scan {result.scan_id}</div>
        {result.payment_summary && (
          <div>
            <div>{inr(result.payment_summary.amount)} to {result.payment_summary.payee_id}</div>
            <div className="muted">
              {result.payment_summary.payee_name || 'Unknown payee'} · {result.payment_summary.merchant_category} · {result.payment_summary.channel}
            </div>
          </div>
        )}
        <div>Score {result.risk_score}/100 · Level {result.risk_level}</div>
        <div>Model backend: {result.model.backend} · Pipeline {result.pipeline_version}</div>
        <div className="muted" style={{ marginTop: 8 }}>
          Browser context (weak signal): {ctx.installId} · {ctx.platform} · {ctx.language} · {ctx.timezone}
        </div>
      </SentinelCard>
      {result.analysis_type === 'payment' && (
        <SentinelCard>
          <h3>Make payment (demo only — no money moves)</h3>
          {paid ? (
            <AlertBanner kind="info" title="Payment recorded locally" subtitle={paid} />
          ) : (
            <SentinelButton onClick={() => (needsConfirm ? setConfirming(true) : doPay())}>
              Make Payment
            </SentinelButton>
          )}
        </SentinelCard>
      )}
      {confirming && (
        <ConfirmDialog
          title={`${result.risk_level === 'HIGH' ? 'High risk' : 'Suspicious'} transaction`}
          body={`${result.recommended_action.headline} Pay ${result.payment_summary ? inr(result.payment_summary.amount) : ''} anyway?`}
          confirmLabel="Pay anyway"
          onConfirm={doPay}
          onCancel={() => setConfirming(false)}
        />
      )}
      <div className="row">
        <Link className="btn" to="/transaction">New Transaction</Link>
        <Link className="btn secondary" to="/dashboard">View Dashboard</Link>
      </div>
    </div>
  );
}

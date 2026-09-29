// pages/TransactionPage — the SentinelPay pay flow, extended with input modes (Slice 3).
// Payment mode is unchanged. Message/Link/QR modes reuse the same card, gates,
// chain poll, and submit pipeline. No new pages, no redesign.
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { analyze, analyzePayment, fetchCategories, verifyChain } from '../api/analyze';
import { ApiError } from '../api/client';
import type { ChainVerify, PaymentContext } from '../api/types';
import BreachDialog from '../components/BreachDialog';
import ScanTypeSelector, { type ScanMode } from '../components/ScanTypeSelector';
import { AlertBanner, SectionHeader, SentinelButton, SentinelCard } from '../components/widgets';
import { FALLBACK_CATEGORIES } from '../lib/constants';
import { checkProbePattern, checkRateLimit, sanitiseNote, validateAmount, validateUpi } from '../lib/gates';
import { checkImageFile, decodePreview, fileToBase64 } from '../lib/qr';
import { readBalance } from '../lib/balance';

export default function TransactionPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<ScanMode>('payment');
  // Payment fields (unchanged behaviour).
  const [balance, setBalance] = useState('');
  const [receiver, setReceiver] = useState('');
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [category, setCategory] = useState(FALLBACK_CATEGORIES[0]);
  const [categories, setCategories] = useState<string[]>(FALLBACK_CATEGORIES);
  // Message / link fields.
  const [messageText, setMessageText] = useState('');
  const [messageContext, setMessageContext] = useState('unknown');
  const [urlText, setUrlText] = useState('');
  // Optional payment context for non-payment modes.
  const [showContext, setShowContext] = useState(false);
  const [ctxAmount, setCtxAmount] = useState('');
  const [ctxBalance, setCtxBalance] = useState('');
  const [ctxPayee, setCtxPayee] = useState('');
  // QR fields.
  const [qrFile, setQrFile] = useState<File | null>(null);
  const [qrPayload, setQrPayload] = useState('');
  const [qrPreview, setQrPreview] = useState('');
  const [qrDecoded, setQrDecoded] = useState<string | null>(null);

  const [warning, setWarning] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [chainOk, setChainOk] = useState<boolean | null>(null);
  const [breach, setBreach] = useState<ChainVerify | null>(null);
  const polling = useRef(false);

  useEffect(() => {
    const stored = readBalance();
    if (stored) setBalance(stored);
    fetchCategories()
      .then((cats) => {
        if (cats.length) {
          setCategories(cats.map((c) => c.label));
          setCategory(cats[0].label);
        }
      })
      .catch(() => undefined);
    const poll = async () => {
      if (polling.current) return; // never overlap requests
      polling.current = true;
      try {
        const v = await verifyChain();
        setChainOk(v.valid);
        setBreach(v.valid ? null : v);
      } catch {
        // Network errors must not raise false breach alarms.
      } finally {
        polling.current = false;
      }
    };
    void poll();
    const timer = setInterval(() => void poll(), 5000);
    return () => clearInterval(timer);
  }, []);

  const paymentContext = (): PaymentContext | undefined => {
    if (!showContext) return undefined;
    const ctx: PaymentContext = {};
    const a = Number(ctxAmount.trim().replace(/,/g, ''));
    const b = Number(ctxBalance.trim().replace(/,/g, ''));
    if (Number.isFinite(a) && a > 0) ctx.amount = a;
    if (Number.isFinite(b) && b > 0) ctx.sender_balance = b;
    if (ctxPayee.trim()) ctx.payee_name = ctxPayee.trim();
    return Object.keys(ctx).length ? ctx : undefined;
  };

  const onQrFile = async (file: File | null) => {
    setQrFile(file);
    setQrDecoded(null);
    setQrPayload('');
    if (!file) {
      setQrPreview('');
      return;
    }
    const problem = checkImageFile(file);
    if (problem) {
      setWarning(problem);
      setQrPreview('');
      return;
    }
    const url = URL.createObjectURL(file);
    setQrPreview(url);
    setQrDecoded(await decodePreview(url));
  };

  const submitPayment = async (): Promise<string | null> => {
    const rate = checkRateLimit();
    if (!rate.allowed) {
      setWarning(`Too many transactions. Wait ${rate.retryAfterSec}s.`);
      return null;
    }
    const upiErr = validateUpi(receiver);
    if (upiErr) {
      setWarning(upiErr);
      return null;
    }
    const amt = validateAmount(amount);
    if (amt.error || amt.amount === undefined) {
      setWarning(amt.error || 'Invalid amount.');
      return null;
    }
    const bal = Number(balance.trim().replace(/,/g, ''));
    if (!Number.isFinite(bal) || bal <= 0) {
      setWarning('Balance must be a positive number.');
      return null;
    }
    const probe = checkProbePattern(amt.amount);
    if (probe) setWarning(probe);
    const result = await analyzePayment({
      amount: amt.amount,
      currency: 'INR',
      payee_id: receiver.trim().toLowerCase(),
      payee_name: 'Unknown',
      sender_balance: bal,
      note: note.trim() ? sanitiseNote(note) : undefined,
      channel: 'upi',
      merchant_category: category,
    });
    return result.scan_id;
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setWarning('');
    setError('');
    setBusy(true);
    try {
      let scanId: string | null = null;
      if (mode === 'payment') {
        scanId = await submitPayment();
      } else if (mode === 'message') {
        if (!messageText.trim()) {
          setWarning('Paste the message text to check.');
          return;
        }
        const ctx = paymentContext();
        scanId = (await analyze({
          analysis_type: 'message',
          message: { text: messageText.trim(), context: messageContext as 'sms' | 'whatsapp' | 'email' | 'unknown' },
          ...(ctx ? { payment_context: ctx } : {}),
        })).scan_id;
      } else if (mode === 'url') {
        if (!urlText.trim()) {
          setWarning('Paste the link to check.');
          return;
        }
        const ctx = paymentContext();
        scanId = (await analyze({
          analysis_type: 'url',
          url: { url: urlText.trim() },
          ...(ctx ? { payment_context: ctx } : {}),
        })).scan_id;
      } else {
        const ctx = paymentContext();
        if (qrFile) {
          const problem = checkImageFile(qrFile);
          if (problem) {
            setWarning(problem);
            return;
          }
          const image_base64 = await fileToBase64(qrFile);
          scanId = (await analyze({
            analysis_type: 'qr',
            qr: { image_base64 },
            ...(ctx ? { payment_context: ctx } : {}),
          })).scan_id;
        } else if (qrPayload.trim()) {
          scanId = (await analyze({
            analysis_type: 'qr',
            qr: { payload: qrPayload.trim() },
            ...(ctx ? { payment_context: ctx } : {}),
          })).scan_id;
        } else {
          setWarning('Choose a QR image or paste its payload text.');
          return;
        }
      }
      if (scanId) navigate(`/result/${scanId}`);
    } catch (err) {
      if (err instanceof ApiError && err.kind === 'validation' && mode === 'payment') {
        setWarning(err.message);
      } else if (err instanceof ApiError && err.kind === 'rate_limited') {
        setWarning(`Server is busy. ${err.message}`);
      } else {
        setError(err instanceof ApiError ? err.message : 'Submission failed.');
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="shell">
      {breach && (
        <BreachDialog brokenAtId={breach.broken_at_id} reason={breach.reason} />
      )}
      <SectionHeader
        title="Check before you pay"
        trailing={
          <span title={chainOk === null ? 'Chain status unknown' : chainOk ? 'Chain intact' : 'Chain broken'}>
            <span className={`chain-dot${chainOk === false ? ' broken' : ''}`} />{' '}
            <Link to="/audit">Audit</Link> · <Link to="/dashboard">Dashboard</Link> · <Link to="/history">History</Link>
          </span>
        }
      />
      <p className="muted">Check a payment, message, link, or QR code before money moves</p>
      {chainOk === false && (
        <AlertBanner kind="danger" title="Chain integrity compromised!" subtitle="Open the audit log to inspect." />
      )}
      {warning && <AlertBanner kind="warn" title="Security notice" subtitle={warning} />}
      {error && (
        <div className="alert alert-danger" role="alert">{error}</div>
      )}
      <ScanTypeSelector mode={mode} onChange={(m) => { setMode(m); setWarning(''); setError(''); }} />
      <SentinelCard>
        <form onSubmit={submit}>
          {mode === 'payment' && (
            <>
              <label htmlFor="balance">Your balance (INR)</label>
              <input id="balance" inputMode="decimal" value={balance} onChange={(e) => setBalance(e.target.value)} placeholder="e.g. 50000" />
              <label htmlFor="receiver">Receiver UPI ID</label>
              <input id="receiver" value={receiver} onChange={(e) => setReceiver(e.target.value)} placeholder="name@bank" />
              <label htmlFor="amount">Amount (INR)</label>
              <input id="amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="e.g. 2500" />
              <label htmlFor="category">Merchant category</label>
              <select id="category" value={category} onChange={(e) => setCategory(e.target.value)}>
                {categories.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
              <label htmlFor="note">Note (optional)</label>
              <textarea id="note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
            </>
          )}
          {mode === 'message' && (
            <>
              <label htmlFor="message">Suspicious message</label>
              <textarea id="message" rows={5} value={messageText} onChange={(e) => setMessageText(e.target.value)} placeholder="Paste the SMS, WhatsApp, or email text…" maxLength={4000} />
              <div className="muted">{messageText.length}/4000</div>
              <label htmlFor="msgctx">Where did it arrive?</label>
              <select id="msgctx" value={messageContext} onChange={(e) => setMessageContext(e.target.value)}>
                <option value="unknown">Unknown</option>
                <option value="sms">SMS</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="email">Email</option>
              </select>
            </>
          )}
          {mode === 'url' && (
            <>
              <label htmlFor="link">Suspicious link</label>
              <input id="link" value={urlText} onChange={(e) => setUrlText(e.target.value)} placeholder="https://…" />
              <p className="muted">Links are inspected statically. Nothing is fetched or opened.</p>
            </>
          )}
          {mode === 'qr' && (
            <>
              <label htmlFor="qrfile">QR image</label>
              <input
                id="qrfile"
                type="file"
                accept="image/*"
                onChange={(e) => void onQrFile(e.target.files ? e.target.files[0] : null)}
              />
              {qrPreview && (
                <div style={{ marginTop: 8 }}>
                  <img src={qrPreview} alt="QR preview" style={{ maxWidth: 180, border: '1px solid var(--border)' }} />
                  <div className="muted">{qrDecoded ? `Preview decoded: ${qrDecoded.slice(0, 80)}` : 'Preview only — the server decodes for the verdict.'}</div>
                </div>
              )}
              <label htmlFor="qrpayload">…or paste a QR payload</label>
              <textarea id="qrpayload" rows={3} value={qrPayload} onChange={(e) => { setQrPayload(e.target.value); setQrFile(null); setQrPreview(''); }} placeholder="upi://pay?pa=… or https://… or plain text" />
            </>
          )}
          {mode !== 'payment' && (
            <>
              <div style={{ marginTop: 12 }}>
                <button type="button" className="secondary" onClick={() => setShowContext((v) => !v)}>
                  {showContext ? 'Hide payment context' : 'Add payment context (optional)'}
                </button>
              </div>
              {showContext && (
                <>
                  <label htmlFor="ctxamount">Linked amount (INR, optional)</label>
                  <input id="ctxamount" inputMode="decimal" value={ctxAmount} onChange={(e) => setCtxAmount(e.target.value)} />
                  <label htmlFor="ctxbalance">Your balance (INR, optional)</label>
                  <input id="ctxbalance" inputMode="decimal" value={ctxBalance} onChange={(e) => setCtxBalance(e.target.value)} />
                  <label htmlFor="ctxpayee">Payee name (optional)</label>
                  <input id="ctxpayee" value={ctxPayee} onChange={(e) => setCtxPayee(e.target.value)} />
                </>
              )}
            </>
          )}
          <div style={{ marginTop: 16 }}>
            <SentinelButton type="submit" disabled={busy}>{busy ? 'Analysing…' : mode === 'payment' ? 'Pay & Analyse' : 'Check'}</SentinelButton>
          </div>
        </form>
      </SentinelCard>
    </div>
  );
}

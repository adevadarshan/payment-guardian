// ResultExtras tests (Slice 3): evidence panel + seen badge rendering.
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ResultPage from './ResultPage';

const base = {
  scan_id: 'scan-q',
  analysis_type: 'qr',
  risk_score: 20,
  risk_level: 'SAFE',
  reasons: [],
  signals: [],
  evidence: {
    extracted_urls: ['http://example.com/a'],
    matched_phrases: ['verify', 'otp'],
    qr_payload: 'upi://pay?pa=shop@upi&pn=Shop',
    decoded: true,
    parsed_qr: { pa: 'shop@upi', pn: 'Shop', am: null, cu: null, tr: null, tn: null, mc: null, rpayee: null },
    payload_class: 'upi_uri',
    qr_decode: 'client',
  },
  seen: { status: 'new', first_seen_at: null, times_seen: 1 },
  recommended_action: { headline: 'Transaction appears legitimate. Proceed normally.', steps: [] },
  advisory: { status: 'disabled', provider: null, text: null },
  model: { backend: 'none', version: null },
  pipeline_version: 'slice-3',
  created_at: new Date().toISOString(),
  payment_summary: null,
};

function renderResult(result: unknown) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async () => ({
    ok: true, status: 200, json: async () => result,
  }) as Response);
  render(
    <MemoryRouter initialEntries={['/result/scan-q']}>
      <Routes>
        <Route path="/result/:id" element={<ResultPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ResultPage extras', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('renders evidence and the new-QR badge with the not-safe note', async () => {
    renderResult(base);
    await waitFor(() => expect(screen.getByText('Evidence')).toBeInTheDocument());
    expect(screen.getByText('http://example.com/a')).toBeInTheDocument();
    expect(screen.getByText('verify')).toBeInTheDocument();
    expect(screen.getByText(/upi:\/\/pay\?pa=shop@upi/)).toBeInTheDocument();
    expect(screen.getByText('pa')).toBeInTheDocument();
    expect(screen.getByText(/new to us/i)).toBeInTheDocument();
    expect(screen.getByText(/not a safe code/i)).toBeInTheDocument();
  });

  it('renders the previously-seen badge', async () => {
    renderResult({
      ...base,
      seen: { status: 'previously_seen', first_seen_at: '2026-09-29T00:00:00+00:00', times_seen: 2 },
    });
    await waitFor(() => expect(screen.getByText(/seen before/i)).toBeInTheDocument());
  });

  it('hides Make Payment for non-payment results', async () => {
    renderResult(base);
    await waitFor(() => expect(screen.getByText('Evidence')).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /make payment/i })).not.toBeInTheDocument();
  });

  it('shows model/advisory status and the advisory note when available', async () => {
    renderResult({
      ...base,
      model: { backend: 'synthetic-v1', version: 'synthetic-v1' },
      advisory: { status: 'ok', provider: 'stub', text: 'Consider pausing here.' },
    });
    await waitFor(() => expect(screen.getByText(/Model: synthetic-v1/)).toBeInTheDocument());
    expect(screen.getByText(/Advisory: available/)).toBeInTheDocument();
    expect(screen.getByText(/not a verdict/i)).toBeInTheDocument();
    expect(screen.getByText('Consider pausing here.')).toBeInTheDocument();
  });

  it('hides the advisory note when disabled', async () => {
    renderResult(base);
    await waitFor(() => expect(screen.getByText('Evidence')).toBeInTheDocument());
    expect(screen.getByText(/Advisory: disabled/)).toBeInTheDocument();
    expect(screen.queryByText(/not a verdict/i)).not.toBeInTheDocument();
  });
});

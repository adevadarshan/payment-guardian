// ResultPage tests (Slice 2): gauge, reasons, action, summary, Make Payment flow.
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { BALANCE_KEY } from '../lib/balance';
import ResultPage from './ResultPage';

const baseResult = {
  scan_id: 'scan-1',
  analysis_type: 'payment',
  risk_score: 75,
  risk_level: 'HIGH',
  reasons: [
    { code: 'payment.amount_tier', signal: 's', title: 'Large transaction amount', observation: 'Amount Rs.12,000 crosses the Rs.10,000 tier', impact: 'high' },
  ],
  signals: [],
  evidence: { extracted_urls: [], matched_phrases: [], qr_payload: null, decoded: false },
  seen: { status: 'not_applicable', first_seen_at: null, times_seen: null },
  recommended_action: { headline: 'Potential fraud detected. Block transaction & alert user.', steps: ['Do not pay.'] },
  advisory: { status: 'disabled', provider: null, text: null },
  model: { backend: 'none', version: null },
  pipeline_version: 'slice-2',
  created_at: new Date().toISOString(),
  payment_summary: {
    amount: 12000, payee_id: 'unknown@upi', payee_name: 'Unknown',
    merchant_category: 'Travel', channel: 'upi', sender_balance: 50000,
  },
};

function renderResult(result: unknown) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async () => ({
    ok: true, status: 200, json: async () => result,
  }) as Response);
  render(
    <MemoryRouter initialEntries={['/result/scan-1']}>
      <Routes>
        <Route path="/result/:id" element={<ResultPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ResultPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('renders score, level, reasons, action, and payment summary', async () => {
    renderResult(baseResult);
    await waitFor(() => expect(screen.getByText('Large transaction amount')).toBeInTheDocument());
    expect(screen.getByText('Potential fraud detected. Block transaction & alert user.')).toBeInTheDocument();
    expect(screen.getAllByText(/Rs\.12,000/).length).toBeGreaterThan(0);
    expect(screen.getByText((_, el) => el?.textContent === 'Unknown · Travel · upi')).toBeInTheDocument();
  });

  it('HIGH Make Payment requires confirmation, then deducts and persists balance', async () => {
    const user = userEvent.setup();
    renderResult(baseResult);
    await waitFor(() => expect(screen.getByRole('button', { name: /make payment/i })).toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: /make payment/i }));
    expect(await screen.findByRole('alertdialog')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /pay anyway/i }));
    await waitFor(() => expect(screen.getByText(/New balance/)).toBeInTheDocument());
    expect(localStorage.getItem(BALANCE_KEY)).toBe('38000');
  });

  it('cancelling the confirm dialog aborts payment', async () => {
    const user = userEvent.setup();
    renderResult(baseResult);
    await waitFor(() => expect(screen.getByRole('button', { name: /make payment/i })).toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: /make payment/i }));
    await user.click(await screen.findByRole('button', { name: /cancel/i }));
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument());
    expect(screen.getByRole('button', { name: /make payment/i })).toBeInTheDocument();
  });

  it('SAFE pays immediately without confirmation', async () => {
    const user = userEvent.setup();
    renderResult({ ...baseResult, risk_score: 5, risk_level: 'SAFE', reasons: [] });
    await waitFor(() => expect(screen.getByRole('button', { name: /make payment/i })).toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: /make payment/i }));
    await waitFor(() => expect(screen.getByText(/New balance/)).toBeInTheDocument());
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });
});

// TransactionPage tests (Slice 1): categories render, submit navigates, error renders.
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TransactionPage from './TransactionPage';

const stubResult = {
  scan_id: 'scan-123',
  analysis_type: 'payment',
  risk_score: 0,
  risk_level: 'SAFE',
  reasons: [{ code: 'pipeline.not_implemented', signal: 'pipeline.stub', title: 't', observation: 'o', impact: 'informational' }],
  signals: [],
  evidence: { extracted_urls: [], matched_phrases: [], qr_payload: null, decoded: false },
  seen: { status: 'not_applicable', first_seen_at: null, times_seen: null },
  recommended_action: { headline: 'h', steps: [] },
  advisory: { status: 'disabled', provider: null, text: null },
  model: { backend: 'none', version: null },
  pipeline_version: 'slice-1',
  created_at: new Date().toISOString(),
};

function mockFetch(handler: (url: string) => { ok: boolean; status?: number; body: unknown }) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input);
    const r = handler(url);
    return { ok: r.ok, status: r.status ?? (r.ok ? 200 : 500), json: async () => r.body } as Response;
  });
}

describe('TransactionPage', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('renders categories from the API', async () => {
    mockFetch((url) => {
      if (url.endsWith('/categories')) return { ok: true, body: [{ label: 'Groceries', key: 'G', type: 'PAYMENT', risk_weight: 0.8 }] };
      if (url.endsWith('/audit/verify')) return { ok: true, body: { valid: true, entry_count: 0 } };
      return { ok: false, body: {} };
    });
    render(
      <MemoryRouter>
        <TransactionPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Groceries')).toBeInTheDocument());
  });

  it('submitting a valid form navigates to the result page', async () => {
    const user = userEvent.setup();
    mockFetch((url) => {
      if (url.endsWith('/categories')) return { ok: true, body: [] };
      if (url.endsWith('/audit/verify')) return { ok: true, body: { valid: true, entry_count: 0 } };
      if (url.endsWith('/analyze')) return { ok: true, body: stubResult };
      return { ok: false, body: {} };
    });
    render(
      <MemoryRouter initialEntries={['/transaction']}>
        <Routes>
          <Route path="/transaction" element={<TransactionPage />} />
          <Route path="/result/:id" element={<div>result-scan-123</div>} />
        </Routes>
      </MemoryRouter>,
    );
    await user.type(screen.getByLabelText(/balance/i), '5000');
    await user.type(screen.getByLabelText(/receiver/i), 'shop@grocery');
    await user.type(screen.getByLabelText(/amount/i), '150');
    await user.click(screen.getByRole('button', { name: 'Pay & Analyse' }));
    await waitFor(() => expect(screen.getByText('result-scan-123')).toBeInTheDocument());
  });

  it('renders a server error message', async () => {    const user = userEvent.setup();
    mockFetch((url) => {
      if (url.endsWith('/categories')) return { ok: true, body: [] };
      if (url.endsWith('/audit/verify')) return { ok: true, body: { valid: true, entry_count: 0 } };
      return { ok: false, status: 500, body: { error: { code: 'server_error', message: 'Boom' } } };
    });
    render(
      <MemoryRouter>
        <TransactionPage />
      </MemoryRouter>,
    );
    await user.type(screen.getByLabelText(/balance/i), '5000');
    await user.type(screen.getByLabelText(/receiver/i), 'shop@grocery');
    await user.type(screen.getByLabelText(/amount/i), '150');
    await user.click(screen.getByRole('button', { name: 'Pay & Analyse' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Boom'));
  });
});

describe("chain polling", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("opens the breach dialog on an invalid chain", async () => {
    mockFetch((url) => {
      if (url.endsWith("/categories")) return { ok: true, body: [] };
      if (url.endsWith("/audit/verify"))
        return { ok: true, body: { valid: false, broken_at_id: 7, reason: "Hash mismatch at entry 7" } };
      return { ok: false, body: {} };
    });
    render(
      <MemoryRouter>
        <TransactionPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByRole("alertdialog")).toBeInTheDocument());
    expect(screen.getByText(/Entry 7/)).toBeInTheDocument();
  });
});

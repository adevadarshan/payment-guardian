// DashboardPage tests (Slice 2): stats-driven tiles, charts sections, alerts, empty state.
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DashboardPage from './DashboardPage';

const stats = { total: 4, safe: 2, medium: 1, high: 1, fraud_rate: 0.25 };
const scans = [
  { scan_id: 'a', analysis_type: 'payment', risk_score: 85, risk_level: 'HIGH', label: 'Rs.9,500 to shop@grocery', created_at: new Date().toISOString() },
  { scan_id: 'b', analysis_type: 'payment', risk_score: 35, risk_level: 'MEDIUM', label: 'Rs.3,500 to vendor@upi', created_at: new Date().toISOString() },
  { scan_id: 'c', analysis_type: 'payment', risk_score: 5, risk_level: 'SAFE', label: 'Rs.150 to shop@grocery', created_at: new Date().toISOString() },
];

function mockApi(statsBody: unknown, scansBody: unknown) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input);
    if (url.includes('/stats')) return { ok: true, status: 200, json: async () => statsBody } as Response;
    return { ok: true, status: 200, json: async () => scansBody } as Response;
  });
}

describe('DashboardPage', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('renders stats tiles, alerts, feed, and chart sections from the API', async () => {
    mockApi(stats, scans);
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Fraud Dashboard')).toBeInTheDocument());
    expect(screen.getByText('25.0%')).toBeInTheDocument();
    expect(screen.getByText('RISK DISTRIBUTION')).toBeInTheDocument();
    expect(screen.getByText('RISK SCORE HISTOGRAM')).toBeInTheDocument();
    expect(screen.getByText(/HIGH RISK — a/)).toBeInTheDocument();
    expect(screen.getByText(/Suspicious — b/)).toBeInTheDocument();
    expect(screen.getAllByText(/Rs\.9,500 to shop@grocery/).length).toBeGreaterThan(0);
    expect(screen.getByText('BY TYPE')).toBeInTheDocument();
  });

  it('shows the empty state with no data', async () => {
    mockApi({ total: 0, safe: 0, medium: 0, high: 0, fraud_rate: 0.0 }, []);
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('No data')).toBeInTheDocument());
    expect(screen.getByText('No transactions yet.')).toBeInTheDocument();
  });
});

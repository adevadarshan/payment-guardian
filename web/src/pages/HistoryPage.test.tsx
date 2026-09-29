// HistoryPage test (Slice 2): server-side level filters, no Clear action.
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import HistoryPage from './HistoryPage';

const requested: string[] = [];

describe('HistoryPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    requested.length = 0;
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      requested.push(String(input));
      return {
        ok: true,
        status: 200,
        json: async () => [
          {
            scan_id: 'scan-abc',
            analysis_type: 'payment',
            risk_score: 0,
            risk_level: 'SAFE',
            label: 'Rs.150 to shop@grocery',
            created_at: new Date().toISOString(),
          },
        ],
      } as Response;
    });
  });

  it('renders scans returned by the API', async () => {
    render(
      <MemoryRouter>
        <HistoryPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/Rs\.150 to shop@grocery/)).toBeInTheDocument());
    expect(screen.getByText('1 transactions')).toBeInTheDocument();
  });

  it('filter chips request the matching level from the server', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <HistoryPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/Rs\.150 to shop@grocery/)).toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: 'High Risk' }));
    await waitFor(() =>
      expect(requested.some((u) => u.includes('level=HIGH'))).toBe(true),
    );
  });

  it('type chips request the matching type from the server', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <HistoryPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/Rs\.150 to shop@grocery/)).toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: 'QR' }));
    await waitFor(() =>
      expect(requested.some((u) => u.includes('type=qr'))).toBe(true),
    );
  });

  it('has no Clear History action', async () => {
    render(
      <MemoryRouter>
        <HistoryPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/Rs\.150 to shop@grocery/)).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /clear/i })).not.toBeInTheDocument();
  });
});

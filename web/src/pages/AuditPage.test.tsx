// AuditPage tests (Slice 2): SCAN_SUBMITTED labels, verify valid/broken.
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AuditPage from './AuditPage';

const entries = [
  {
    id: 1, event_type: 'SCAN_SUBMITTED', entity_type: 'scan', entity_id: 'scan-1',
    payload: {}, previous_hash: '0'.repeat(64), entry_hash: 'a'.repeat(64),
    created_at: new Date().toISOString(),
  },
];

function mockApi(verifyBody: unknown) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.includes('/audit/verify')) return { ok: true, status: 200, json: async () => verifyBody } as Response;
    if ((init as RequestInit)?.method === 'POST') return { ok: true, status: 200, json: async () => verifyBody } as Response;
    return { ok: true, status: 200, json: async () => entries } as Response;
  });
}

describe('AuditPage', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('renders SCAN_SUBMITTED entries with labels and verifies valid chain', async () => {
    const user = userEvent.setup();
    mockApi({ valid: true, entry_count: 1 });
    render(
      <MemoryRouter>
        <AuditPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/#1 Scan submitted/)).toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: /verify chain integrity/i }));
    await waitFor(() => expect(screen.getByText(/Chain valid — 1 entries/)).toBeInTheDocument());
  });

  it('renders the broken-chain state', async () => {
    const user = userEvent.setup();
    mockApi({ valid: false, broken_at_id: 1, reason: 'Hash mismatch at entry 1' });
    render(
      <MemoryRouter>
        <AuditPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/#1 Scan submitted/)).toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: /verify chain integrity/i }));
    await waitFor(() => expect(screen.getByText(/Chain broken at entry 1/)).toBeInTheDocument());
  });
});

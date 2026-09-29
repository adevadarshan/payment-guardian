// TransactionModes tests (Slice 3): the four input modes submit correct payloads.
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TransactionPage from './TransactionPage';

const posted: { url: string; body: unknown }[] = [];

function mockApi() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith('/categories')) {
      return { ok: true, status: 200, json: async () => [] } as Response;
    }
    if (url.endsWith('/audit/verify')) {
      return { ok: true, status: 200, json: async () => ({ valid: true, entry_count: 0 }) } as Response;
    }
    posted.push({ url, body: JSON.parse(String((init as RequestInit)?.body || '{}')) });
    return {
      ok: true, status: 200, json: async () => ({ scan_id: 'scan-x' }),
    } as Response;
  });
}

function renderPage() {
  render(
    <MemoryRouter initialEntries={['/transaction']}>
      <Routes>
        <Route path="/transaction" element={<TransactionPage />} />
        <Route path="/result/:id" element={<div>result-page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('TransactionPage modes', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    posted.length = 0;
  });

  it('message mode posts a discriminated message payload', async () => {
    const user = userEvent.setup();
    mockApi();
    renderPage();
    await user.click(screen.getByRole('button', { name: 'Message' }));
    await user.type(screen.getByLabelText(/suspicious message/i), 'Your account will be blocked now');
    await user.click(screen.getByRole('button', { name: /^check$/i }));
    await waitFor(() => expect(screen.getByText('result-page')).toBeInTheDocument());
    const analyze = posted.find((p) => p.url.endsWith('/analyze'));
    expect(analyze?.body).toMatchObject({
      analysis_type: 'message',
      message: { text: 'Your account will be blocked now' },
    });
  });

  it('link mode posts a discriminated url payload', async () => {
    const user = userEvent.setup();
    mockApi();
    renderPage();
    await user.click(screen.getByRole('button', { name: 'Link' }));
    await user.type(screen.getByLabelText(/suspicious link/i), 'https://example.com/a');
    await user.click(screen.getByRole('button', { name: /^check$/i }));
    await waitFor(() => expect(screen.getByText('result-page')).toBeInTheDocument());
    const analyze = posted.find((p) => p.url.endsWith('/analyze'));
    expect(analyze?.body).toMatchObject({
      analysis_type: 'url',
      url: { url: 'https://example.com/a' },
    });
  });

  it('qr mode posts a pasted payload', async () => {
    const user = userEvent.setup();
    mockApi();
    renderPage();
    await user.click(screen.getByRole('button', { name: 'QR' }));
    await user.type(screen.getByLabelText(/paste a qr payload/i), 'upi://pay?pa=x@y');
    await user.click(screen.getByRole('button', { name: /^check$/i }));
    await waitFor(() => expect(screen.getByText('result-page')).toBeInTheDocument());
    const analyze = posted.find((p) => p.url.endsWith('/analyze'));
    expect(analyze?.body).toMatchObject({
      analysis_type: 'qr',
      qr: { payload: 'upi://pay?pa=x@y' },
    });
  });

  it('qr mode warns when neither file nor payload is given', async () => {
    const user = userEvent.setup();
    mockApi();
    renderPage();
    await user.click(screen.getByRole('button', { name: 'QR' }));
    await user.click(screen.getByRole('button', { name: /^check$/i }));
    await waitFor(() =>
      expect(screen.getByText(/choose a qr image or paste/i)).toBeInTheDocument(),
    );
    expect(posted.filter((p) => p.url.endsWith('/analyze'))).toHaveLength(0);
  });
});

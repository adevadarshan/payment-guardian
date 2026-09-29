// components/EvidencePanel.tsx — urls, phrases, decoded payload, parsed UPI (Slice 3).
import type { Evidence } from '../api/types';

export default function EvidencePanel({ evidence }: { evidence: Evidence }) {
  const hasUrls = evidence.extracted_urls.length > 0;
  const hasPhrases = evidence.matched_phrases.length > 0;
  const hasQr = evidence.qr_payload !== null && evidence.qr_payload !== undefined;
  const parsedEntries = Object.entries(evidence.parsed_qr || {}).filter(([, v]) => v !== null && v !== '');
  if (!hasUrls && !hasPhrases && !hasQr && parsedEntries.length === 0) return null;
  return (
    <div>
      <h3>Evidence</h3>
      {hasUrls && (
        <>
          <div className="muted">Links found</div>
          <ul className="mono">
            {evidence.extracted_urls.map((u) => (
              <li key={u}>{u}</li>
            ))}
          </ul>
        </>
      )}
      {hasPhrases && (
        <>
          <div className="muted">Matched phrases</div>
          <div className="chips">
            {evidence.matched_phrases.map((p) => (
              <span key={p} className="badge badge-neutral">{p}</span>
            ))}
          </div>
        </>
      )}
      {hasQr && (
        <>
          <div className="muted">Decoded QR payload{evidence.payload_class ? ` (${evidence.payload_class})` : ''}</div>
          <pre className="mono" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{evidence.qr_payload}</pre>
        </>
      )}
      {parsedEntries.length > 0 && (
        <>
          <div className="muted">UPI fields</div>
          <table className="scan-table">
            <tbody>
              {parsedEntries.map(([k, v]) => (
                <tr key={k}>
                  <td className="mono">{k}</td>
                  <td className="mono">{String(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

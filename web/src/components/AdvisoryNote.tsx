// components/AdvisoryNote.tsx — labelled advisory text (Slice 4).
// Rendered only when advisory.status == "ok". Never a verdict.
export default function AdvisoryNote({ text, provider }: { text: string; provider: string | null }) {
  return (
    <div className="alert alert-info" role="note" aria-label="Advisory note">
      <strong>Advisory — not a verdict{provider ? ` (${provider})` : ''}</strong>
      <div>{text}</div>
    </div>
  );
}

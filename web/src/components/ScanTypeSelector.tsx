// components/ScanTypeSelector.tsx — Payment/Message/Link/QR control (Slice 3).
// Same tokens, no new visual system.
export type ScanMode = 'payment' | 'message' | 'url' | 'qr';

const MODES: { value: ScanMode; label: string }[] = [
  { value: 'payment', label: 'Payment' },
  { value: 'message', label: 'Message' },
  { value: 'url', label: 'Link' },
  { value: 'qr', label: 'QR' },
];

export default function ScanTypeSelector({ mode, onChange }: { mode: ScanMode; onChange: (m: ScanMode) => void }) {
  return (
    <div className="chips" role="group" aria-label="What to check">
      {MODES.map((m) => (
        <button key={m.value} className={mode === m.value ? '' : 'secondary'} onClick={() => onChange(m.value)}>
          {m.label}
        </button>
      ))}
    </div>
  );
}

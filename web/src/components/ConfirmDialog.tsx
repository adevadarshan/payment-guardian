// components/ConfirmDialog.tsx — generic confirm modal in card style (Slice 2).
export default function ConfirmDialog({
  title, body, confirmLabel, onConfirm, onCancel,
}: {
  title: string; body: string; confirmLabel: string;
  onConfirm: () => void; onCancel: () => void;
}) {
  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-label={title}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50,
      }}
    >
      <div className="card" style={{ maxWidth: 440 }}>
        <h2>{title}</h2>
        <p>{body}</p>
        <div className="row">
          <button onClick={onConfirm}>{confirmLabel}</button>
          <button className="secondary" onClick={onCancel}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

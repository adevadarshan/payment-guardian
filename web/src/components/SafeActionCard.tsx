// components/SafeActionCard.tsx — headline + steps (Slice 2). Copy comes from the API.
export default function SafeActionCard({ headline, steps }: { headline: string; steps: string[] }) {
  return (
    <div>
      <p><strong>{headline}</strong></p>
      <ul>
        {steps.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ul>
    </div>
  );
}

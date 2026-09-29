// components/SeenStatusBadge.tsx — previously_seen/new/unable_to_verify (Slice 3).
// Fixed copy. A new code is never presented as safe.
import type { SeenInfo } from '../api/types';

export default function SeenStatusBadge({ seen }: { seen: SeenInfo }) {
  if (seen.status === 'previously_seen') {
    return (
      <div className="alert alert-info" role="status">
        <strong>Seen before</strong>
        <div>
          First scanned {seen.first_seen_at ? new Date(seen.first_seen_at).toLocaleString() : 'previously'}
          {seen.times_seen ? ` · ${seen.times_seen} times` : ''}. Repeated sightings are common for
          legitimate merchant codes.
        </div>
      </div>
    );
  }
  if (seen.status === 'new') {
    return (
      <div className="alert alert-info" role="status">
        <strong>New to us — no history for this code</strong>
        <div>A new code is not a safe code. Anyone can generate a QR.</div>
      </div>
    );
  }
  if (seen.status === 'unable_to_verify') {
    return (
      <div className="alert alert-warn" role="alert">
        <strong>Could not read this code</strong>
        <div>We cannot tell what it does. Do not scan it again elsewhere.</div>
      </div>
    );
  }
  return null;
}

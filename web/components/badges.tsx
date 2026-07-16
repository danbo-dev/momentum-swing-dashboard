import type { Bucket, CatalystDetail, Playbook } from "@/lib/types";
import { bucketLabel } from "@/lib/format";

// Entry-playbook tag. Continuation = established uptrend; Reversal = earlier turn
// (tighter stop). Icon + label so color never carries meaning alone.
export function PlaybookBadge({ playbook }: { playbook: Playbook | null }) {
  if (!playbook) return <span className="muted">—</span>;
  const cont = playbook === "continuation";
  return (
    <span
      className="badge"
      title={cont ? "Continuation — established uptrend entry" : "Early reversal — turn from oversold (tighter stop)"}
      style={{ color: cont ? "var(--f-momentum)" : "var(--serious)" }}
    >
      {cont ? "➔ Continuation" : "↺ Reversal"}
    </span>
  );
}

export const statusClass: Record<string, string> = {
  green: "status-good",
  yellow: "status-warning",
  orange: "status-serious",
  red: "status-critical",
};

export function BucketBadge({ bucket }: { bucket: Bucket }) {
  if (bucket === "none") return <span className="muted">—</span>;
  const icon = bucket === "strong_buy" ? "▲" : "◇";
  return <span className={`badge ${bucket}`}>{icon} {bucketLabel[bucket]}</span>;
}

// Earnings within the "soon" window is a warning (event risk over a swing hold),
// shipped with an icon + label so color never carries meaning alone.
export function EarningsBadge({ c }: { c: CatalystDetail }) {
  if (c.days_to_earnings == null) return <span className="muted">—</span>;
  const soon = c.earnings_soon;
  const title = c.earnings_date ? `Earnings ${c.earnings_date}` : undefined;
  if (soon) {
    return (
      <span className="badge status-warning" title={title}>
        ⚠ {c.days_to_earnings}d
      </span>
    );
  }
  return (
    <span className="badge" title={title} style={{ color: "var(--text-2)" }}>
      📅 {c.days_to_earnings}d
    </span>
  );
}

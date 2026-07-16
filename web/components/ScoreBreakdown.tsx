import type { FactorKey } from "@/lib/types";

const FACTORS: { key: FactorKey; label: string; color: string }[] = [
  { key: "momentum", label: "Momentum", color: "var(--f-momentum)" },
  { key: "trend", label: "Trend", color: "var(--f-trend)" },
  { key: "catalyst", label: "Catalyst", color: "var(--f-catalyst)" },
  { key: "trigger", label: "Trigger", color: "var(--f-trigger)" },
];

// Stacked contribution bar (0..100). Segments sum to the composite score; the
// remainder is an empty track. 2px surface gaps separate adjacent fills.
export default function ScoreBreakdown({
  contributions,
  score,
  compact = false,
}: {
  contributions: Record<FactorKey, number>;
  score: number;
  compact?: boolean;
}) {
  const h = compact ? 8 : 14;
  return (
    <div style={{ width: "100%" }}>
      <div
        style={{
          display: "flex",
          gap: 2,
          height: h,
          background: "var(--grid)",
          borderRadius: 4,
          overflow: "hidden",
        }}
        role="img"
        aria-label={`Composite score ${score} of 100`}
      >
        {FACTORS.map((f) => {
          const w = Math.max(0, contributions[f.key] ?? 0);
          if (w <= 0) return null;
          return (
            <div
              key={f.key}
              title={`${f.label}: ${w.toFixed(1)} pts`}
              style={{ width: `${w}%`, background: f.color }}
            />
          );
        })}
      </div>
      {!compact && (
        <div className="row" style={{ gap: 14, marginTop: 8 }}>
          {FACTORS.map((f) => (
            <span key={f.key} className="row" style={{ gap: 5 }}>
              <span className="dot" style={{ background: f.color }} />
              <span className="sec2">{f.label}</span>
              <span className="tnum" style={{ fontWeight: 600 }}>
                {(contributions[f.key] ?? 0).toFixed(1)}
              </span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

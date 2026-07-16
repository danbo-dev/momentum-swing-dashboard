import type { SnapshotItem } from "@/lib/types";

// Diverging color (blue up / red down) by 1-month return, grouped by sector so
// you can see where money is rotating. Neutral gray midpoint = ~flat.
function color(change: number): string {
  const cap = 20; // saturate at +/-20%
  const t = Math.max(-1, Math.min(1, change / cap));
  if (Math.abs(t) < 0.06) return "var(--div-mid)";
  const pole = t > 0 ? "var(--div-pos)" : "var(--div-neg)";
  const pctMix = Math.round(18 + Math.abs(t) * 62); // 18%..80%
  return `color-mix(in srgb, ${pole} ${pctMix}%, var(--surface-1))`;
}

export default function SectorHeatmap({ snapshot }: { snapshot: SnapshotItem[] }) {
  const bySector = new Map<string, SnapshotItem[]>();
  for (const s of snapshot) {
    if (!bySector.has(s.sector)) bySector.set(s.sector, []);
    bySector.get(s.sector)!.push(s);
  }
  // sort sectors by average 1-month return (hottest first)
  const sectors = [...bySector.entries()]
    .map(([name, items]) => ({
      name,
      items: items.sort((a, b) => b.change_21d - a.change_21d),
      avg: items.reduce((s, i) => s + i.change_21d, 0) / items.length,
    }))
    .sort((a, b) => b.avg - a.avg);

  return (
    <div className="card">
      <div className="row spread">
        <div className="section-title" style={{ margin: 0 }}>Sector Rotation · 1-Month Return</div>
        <div className="row muted" style={{ gap: 6, fontSize: 11 }}>
          <span>−20%</span>
          <span style={{ width: 60, height: 8, borderRadius: 2,
            background: "linear-gradient(90deg, var(--div-neg), var(--div-mid), var(--div-pos))" }} />
          <span>+20%</span>
        </div>
      </div>
      <div style={{ display: "grid", gap: 10, marginTop: 10 }}>
        {sectors.map((sec) => (
          <div key={sec.name}>
            <div className="row spread" style={{ fontSize: 12, marginBottom: 4 }}>
              <span className="sec2" style={{ fontWeight: 600 }}>{sec.name}</span>
              <span className={`tnum ${sec.avg >= 0 ? "pos" : "neg"}`}>
                {sec.avg > 0 ? "+" : ""}{sec.avg.toFixed(1)}%
              </span>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
              {sec.items.map((it) => (
                <span
                  key={it.ticker}
                  title={`${it.ticker}  ${it.change_21d > 0 ? "+" : ""}${it.change_21d}% · score ${it.score}`}
                  style={{
                    background: color(it.change_21d),
                    border: "1px solid var(--border)",
                    borderRadius: 4,
                    padding: "3px 7px",
                    fontSize: 11,
                    fontWeight: 600,
                    color: "var(--text-1)",
                  }}
                >
                  {it.ticker}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

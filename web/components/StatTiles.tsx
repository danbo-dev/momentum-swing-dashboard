import type { Results } from "@/lib/types";

export default function StatTiles({ r }: { r: Results }) {
  const f = r.universe.funnel;
  const tiles = [
    { k: "Strong Buy", v: r.buckets.strong_buy, color: "var(--good)" },
    { k: "Watch", v: r.buckets.watch, color: "var(--f-momentum)" },
    // In funnel mode the "universe" is the whole-market base list, not the
    // narrowed deep-dive set; fall back to `considered` on the seed list.
    { k: "Universe", v: (f ? f.base : r.universe.considered).toLocaleString() },
    { k: "Passed Liquidity", v: r.universe.passed_liquidity },
    { k: "Passed Quality", v: r.universe.passed_quality },
    {
      k: "Regime",
      v: r.market_regime.label,
      color: r.market_regime.risk_on ? "var(--good)" : "var(--serious)",
      small: true,
    },
  ];
  return (
    <>
      <div className="tiles">
        {tiles.map((t) => (
          <div className="tile" key={t.k}>
            <div className="v" style={{ color: t.color, fontSize: t.small ? 20 : undefined }}>
              {t.v}
            </div>
            <div className="k">{t.k}</div>
          </div>
        ))}
      </div>
      {f && (
        <div className="muted" style={{ fontSize: 12, margin: "6px 2px 0" }}>
          Whole-market funnel: {f.base.toLocaleString()} base →{" "}
          {f.screened.toLocaleString()} screened → {f.bucket} bucket →{" "}
          {r.universe.passed_quality} scored
          {f.capped_by_max_bucket && f.momentum_pct_floor != null
            ? ` · momentum floor ${f.momentum_pct_floor}% excess (max-bucket backstop)`
            : ""}
        </div>
      )}
    </>
  );
}

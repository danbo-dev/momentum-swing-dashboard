import { money } from "@/lib/format";
import type { Breadth, MarketRegime } from "@/lib/types";

function Meter({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="row spread" style={{ fontSize: 12 }}>
        <span className="sec2">{label}</span>
        <span className="tnum" style={{ fontWeight: 600 }}>{value}%</span>
      </div>
      <div style={{ height: 6, background: "var(--grid)", borderRadius: 3, marginTop: 3 }}>
        <div style={{
          width: `${value}%`, height: "100%", borderRadius: 3,
          background: value >= 50 ? "var(--f-momentum)" : "var(--serious)",
        }} />
      </div>
    </div>
  );
}

export default function RegimePanel({ regime, breadth }: { regime: MarketRegime; breadth: Breadth }) {
  const riskOn = regime.risk_on;
  return (
    <div className="card">
      <div className="section-title">Market Regime &amp; Breadth</div>
      <div className="row spread" style={{ marginBottom: 12 }}>
        <span className="row" style={{ gap: 8 }}>
          <span className={`dot ${riskOn ? "green" : "orange"}`} style={{ width: 12, height: 12 }} />
          <span style={{ fontSize: 20, fontWeight: 680 }}>{regime.label}</span>
        </span>
        <span className="muted tnum" style={{ fontSize: 12 }}>
          {regime.benchmark} {money(regime.price)} vs {regime.ma} MA{regime.ma_rising ? " ↑" : " ↓"}
        </span>
      </div>
      <div style={{ display: "grid", gap: 10 }}>
        <Meter label="Names above 200-day MA" value={breadth.pct_above_slow_ma} />
        <Meter label="In an uptrend (50 &gt; 200)" value={breadth.pct_uptrend} />
        <Meter label="Advancing today" value={breadth.pct_advancing} />
      </div>
      <div className="muted" style={{ marginTop: 10, fontSize: 12 }}>
        {riskOn
          ? "Benchmark in an uptrend — new long swings are favored."
          : "Benchmark below its long MA — new longs are throttled (scores damped)."}
      </div>
    </div>
  );
}

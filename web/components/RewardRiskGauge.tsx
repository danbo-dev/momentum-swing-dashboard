import { money } from "@/lib/format";
import type { RiskBlock } from "@/lib/types";

// The core buy-decision visual: stop -> entry -> target on one axis, with the
// risk arm (red) and reward arm (green) sized to scale, plus the R:R ratio.
export default function RewardRiskGauge({ risk }: { risk: RiskBlock }) {
  const { stop, entry, target, reward_risk } = risk;
  const span = target - stop || 1;
  const entryFrac = Math.min(1, Math.max(0, (entry - stop) / span));

  return (
    <div>
      <div className="row spread" style={{ marginBottom: 6 }}>
        <span className="section-title" style={{ margin: 0 }}>Reward : Risk</span>
        <span className="badge" style={{
          color: reward_risk >= 2 ? "var(--good)" : "var(--serious)",
          borderColor: "var(--border)",
        }}>
          {reward_risk.toFixed(1)} : 1
        </span>
      </div>
      <div style={{ display: "flex", height: 12, borderRadius: 4, overflow: "hidden", gap: 2 }}>
        <div style={{ width: `${entryFrac * 100}%`, background: "var(--critical)" }}
          title={`Risk ${risk.stop_pct}%`} />
        <div style={{ width: `${(1 - entryFrac) * 100}%`, background: "var(--good)" }}
          title={`Reward ${risk.target_pct}%`} />
      </div>
      <div className="row spread tnum" style={{ marginTop: 6, fontSize: 12 }}>
        <span className="neg">Stop {money(stop)} <span className="muted">({risk.stop_pct}%)</span></span>
        <span style={{ fontWeight: 600 }}>Entry {money(entry)}</span>
        <span className="pos">Target {money(target)} <span className="muted">(+{risk.target_pct}%)</span></span>
      </div>
      <div className="muted tnum" style={{ marginTop: 6, fontSize: 12 }}>
        Suggested: {risk.suggested_shares} sh · {money(risk.suggested_dollars)} · ATR {risk.atr}
      </div>
    </div>
  );
}

import type { Backtest } from "@/lib/types";

const VERDICT: Record<string, { label: string; cls: string }> = {
  positive_edge: { label: "Positive edge", cls: "status-good" },
  weak_positive: { label: "Weak positive", cls: "status-warning" },
  no_edge: { label: "No edge", cls: "status-serious" },
  inconclusive: { label: "Inconclusive", cls: "status-warning" },
};

export default function BacktestPanel({ bt }: { bt: Backtest | null }) {
  if (!bt || bt.error || !bt.quantiles?.length) {
    return (
      <div className="card">
        <div className="section-title">Backtest</div>
        <div className="muted">{bt?.error ?? "No backtest data yet."}</div>
      </div>
    );
  }
  const qs = bt.quantiles;
  const maxAbs = Math.max(...qs.map((q) => Math.abs(q.avg_fwd_ret_pct)), 0.01);
  const v = VERDICT[bt.verdict ?? "inconclusive"] ?? VERDICT.inconclusive;

  return (
    <div className="card">
      <div className="row spread">
        <div className="section-title" style={{ margin: 0 }}>
          Backtest · {bt.params?.horizon_days}-day forward return by score quantile
        </div>
        <span className={`badge ${v.cls}`}>{v.label}</span>
      </div>

      <div style={{ display: "grid", gap: 6, marginTop: 12 }}>
        {[...qs].reverse().map((q) => {
          const w = (Math.abs(q.avg_fwd_ret_pct) / maxAbs) * 100;
          const positive = q.avg_fwd_ret_pct >= 0;
          const top = q.quantile === qs.length;
          return (
            <div className="row" key={q.quantile} style={{ gap: 8 }}>
              <span className="muted tnum" style={{ width: 78, fontSize: 12 }}>
                Q{q.quantile}{top ? " (top)" : q.quantile === 1 ? " (bot)" : ""}
              </span>
              <div style={{ flex: 1, background: "var(--grid)", borderRadius: 4, height: 16 }}>
                <div style={{
                  width: `${w}%`, height: "100%", borderRadius: 4,
                  background: positive ? "var(--f-momentum)" : "var(--critical)",
                }} />
              </div>
              <span className="tnum" style={{ width: 96, textAlign: "right", fontSize: 12 }}>
                {q.avg_fwd_ret_pct > 0 ? "+" : ""}{q.avg_fwd_ret_pct}%
                <span className="muted"> · {q.win_rate_pct}% win</span>
              </span>
            </div>
          );
        })}
      </div>

      <div className="row" style={{ gap: 20, marginTop: 12, fontSize: 12 }}>
        <span><span className="muted">Rank IC </span><b className="tnum">{bt.mean_rank_ic}</b></span>
        <span><span className="muted">Top−bottom </span>
          <b className={`tnum ${(bt.long_short_spread_pct ?? 0) >= 0 ? "pos" : "neg"}`}>
            {(bt.long_short_spread_pct ?? 0) > 0 ? "+" : ""}{bt.long_short_spread_pct}%
          </b>
        </span>
        <span><span className="muted">Obs </span><b className="tnum">{bt.n_observations}</b></span>
        <span className="muted">cost {bt.params?.cost_bps}bps</span>
      </div>
      <div className="muted" style={{ marginTop: 8, fontSize: 11 }}>
        Price-based score (momentum + trend + trigger) reconstructed as-of each past date.
        Positive rank IC and a rising Q1→Q5 pattern indicate the score ranks future winners.
      </div>
    </div>
  );
}

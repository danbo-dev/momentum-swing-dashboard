"use client";
import { money, pct, signedMoney } from "@/lib/format";
import type { PaperStats } from "@/lib/paper";

function Tile({
  k,
  v,
  color,
  sub,
}: {
  k: string;
  v: string;
  color?: string;
  sub?: string;
}) {
  return (
    <div className="tile">
      <div className="v tnum" style={{ color, fontSize: 22 }}>{v}</div>
      <div className="k">{k}</div>
      {sub && <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

const posNeg = (n: number) => (n > 0 ? "var(--pos)" : n < 0 ? "var(--neg)" : undefined);

export default function PaperStatsView({ s }: { s: PaperStats }) {
  if (s.closedCount === 0) {
    return (
      <div className="muted" style={{ fontSize: 13 }}>
        No closed trades yet — sell a position to start building your track record. Win rate,
        expectancy, profit factor and R-multiple stats appear here.
      </div>
    );
  }
  const pf = s.profitFactor;
  return (
    <div className="tiles">
      <Tile k="Closed trades" v={String(s.closedCount)} sub={`${s.wins}W · ${s.losses}L`} />
      <Tile k="Win rate" v={`${s.winRatePct.toFixed(0)}%`} color={posNeg(s.winRatePct - 50)} />
      <Tile k="Realized P&L" v={signedMoney(s.totalRealized)} color={posNeg(s.totalRealized)} />
      <Tile
        k="Expectancy"
        v={s.expectancyR == null ? "—" : `${s.expectancyR >= 0 ? "+" : "−"}${Math.abs(s.expectancyR).toFixed(2)}R`}
        color={s.expectancyR == null ? undefined : posNeg(s.expectancyR)}
        sub="avg R per trade"
      />
      <Tile
        k="Profit factor"
        v={pf == null ? "—" : pf === Infinity ? "∞" : pf.toFixed(2)}
        color={pf != null && pf !== Infinity ? posNeg(pf - 1) : "var(--pos)"}
        sub="gross win / loss"
      />
      <Tile k="Avg win" v={pct(s.avgWinPct)} color="var(--pos)" />
      <Tile k="Avg loss" v={pct(s.avgLossPct)} color="var(--neg)" />
      <Tile
        k="Avg R"
        v={s.avgR == null ? "—" : `${s.avgR >= 0 ? "+" : "−"}${Math.abs(s.avgR).toFixed(2)}R`}
        color={s.avgR == null ? undefined : posNeg(s.avgR)}
      />
      <Tile k="Avg hold" v={`${s.avgHoldDays.toFixed(0)}d`} />
      <Tile
        k="Best / worst"
        v={`${s.bestPct != null ? pct(s.bestPct) : "—"}`}
        sub={s.worstPct != null ? `worst ${pct(s.worstPct)}` : undefined}
        color="var(--pos)"
      />
      <Tile k="Max drawdown" v={`−${s.maxDrawdownPct.toFixed(1)}%`} color={s.maxDrawdownPct > 0 ? "var(--neg)" : undefined} sub="realized equity" />
    </div>
  );
}

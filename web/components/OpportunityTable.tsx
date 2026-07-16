"use client";
import { useMemo, useState } from "react";
import { money, pct } from "@/lib/format";
import type { Opportunity, Playbook } from "@/lib/types";
import Sparkline from "./Sparkline";
import ScoreBreakdown from "./ScoreBreakdown";
import RewardRiskGauge from "./RewardRiskGauge";
import { BucketBadge, EarningsBadge, PlaybookBadge } from "./badges";
import { usePaper } from "./PaperProvider";

type PbFilter = "all" | Playbook;
const PB_TABS: { key: PbFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "continuation", label: "➔ Continuation" },
  { key: "reversal", label: "↺ Reversal" },
];

type Key =
  | "ticker" | "price" | "score" | "momentum_percentile"
  | "trend" | "rsi" | "change_5d" | "change_21d" | "reward_risk";

const COLS: { key: Key; label: string; num: boolean; get: (o: Opportunity) => number | string }[] = [
  { key: "ticker", label: "Ticker", num: false, get: (o) => o.ticker },
  { key: "price", label: "Price", num: true, get: (o) => o.price },
  { key: "score", label: "Score", num: true, get: (o) => o.score },
  { key: "momentum_percentile", label: "Mom %ile", num: true, get: (o) => o.momentum_percentile },
  { key: "trend", label: "Trend", num: true, get: (o) => o.sub_scores.trend },
  { key: "rsi", label: "RSI", num: true, get: (o) => o.rsi },
  { key: "change_5d", label: "5D", num: true, get: (o) => o.change_5d },
  { key: "change_21d", label: "1M", num: true, get: (o) => o.change_21d },
  { key: "reward_risk", label: "R:R", num: true, get: (o) => o.reward_risk },
];

export default function OpportunityTable({ rows }: { rows: Opportunity[] }) {
  const [sortKey, setSortKey] = useState<Key>("score");
  const [asc, setAsc] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [pb, setPb] = useState<PbFilter>("all");

  const counts = useMemo(() => ({
    all: rows.length,
    continuation: rows.filter((o) => o.playbooks?.includes("continuation")).length,
    reversal: rows.filter((o) => o.playbooks?.includes("reversal")).length,
  }), [rows]);

  const sorted = useMemo(() => {
    const col = COLS.find((c) => c.key === sortKey)!;
    const filtered = pb === "all" ? rows : rows.filter((o) => o.playbooks?.includes(pb));
    return [...filtered].sort((a, b) => {
      const av = col.get(a), bv = col.get(b);
      const cmp = typeof av === "number" && typeof bv === "number"
        ? av - bv
        : String(av).localeCompare(String(bv));
      return asc ? cmp : -cmp;
    });
  }, [rows, sortKey, asc, pb]);

  function sortBy(k: Key) {
    if (k === sortKey) setAsc(!asc);
    else { setSortKey(k); setAsc(false); }
  }

  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <div className="row" style={{ gap: 6, padding: "8px 10px", flexWrap: "wrap" }}>
        {PB_TABS.map((t) => (
          <button
            key={t.key}
            className={`btn sm ${pb === t.key ? "primary" : ""}`}
            onClick={() => setPb(t.key)}
          >
            {t.label} <span className="muted">({counts[t.key]})</span>
          </button>
        ))}
      </div>
      <div style={{ overflowX: "auto" }}>
        <table className="tbl">
          <thead>
            <tr>
              {COLS.map((c) => (
                <th key={c.key} className={c.num ? "" : "l"} onClick={() => sortBy(c.key)}>
                  {c.label}{sortKey === c.key ? (asc ? " ▲" : " ▼") : ""}
                </th>
              ))}
              <th className="l">Playbook</th>
              <th>Signal</th>
              <th>Earnings</th>
              <th className="l">30-day trend</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((o) => {
              const isOpen = open === o.ticker;
              return (
                <FragmentRow key={o.ticker} o={o} isOpen={isOpen}
                  onToggle={() => setOpen(isOpen ? null : o.ticker)} />
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FragmentRow({ o, isOpen, onToggle }: { o: Opportunity; isOpen: boolean; onToggle: () => void }) {
  const { openBuy } = usePaper();
  return (
    <>
      <tr className="rowbtn" onClick={onToggle}>
        <td className="l">
          <div style={{ fontWeight: 650 }}>{o.ticker} {isOpen ? "▾" : "▸"}</div>
          <div className="muted" style={{ fontSize: 11 }}>{o.sector}</div>
        </td>
        <td className="tnum">{money(o.price)}</td>
        <td className="tnum" style={{ fontWeight: 650 }}>{o.score}</td>
        <td className="tnum">{o.momentum_percentile}</td>
        <td className="tnum">{o.sub_scores.trend.toFixed(2)}</td>
        <td className="tnum">{o.rsi}</td>
        <td className={`tnum ${o.change_5d >= 0 ? "pos" : "neg"}`}>{pct(o.change_5d)}</td>
        <td className={`tnum ${o.change_21d >= 0 ? "pos" : "neg"}`}>{pct(o.change_21d)}</td>
        <td className="tnum" style={{ color: o.reward_risk >= 2 ? "var(--good)" : "var(--serious)" }}>
          {o.reward_risk.toFixed(1)}
        </td>
        <td className="l"><PlaybookBadge playbook={o.playbook} /></td>
        <td><BucketBadge bucket={o.bucket} /></td>
        <td><EarningsBadge c={o.catalyst_detail} /></td>
        <td className="l"><Sparkline spark={o.spark} /></td>
      </tr>
      {isOpen && (
        <tr className="detail">
          <td colSpan={13}>
            <div className="detail-grid">
              <div>
                <div className="section-title">Why this scores {o.score}</div>
                <ScoreBreakdown contributions={o.contributions} score={o.score} />
                <div className="muted" style={{ marginTop: 10, fontSize: 12 }}>
                  Momentum percentile {o.momentum_percentile} · trigger:{" "}
                  <b>{o.trigger_detail.state.replace(/_/g, " ")}</b> (RSI {o.trigger_detail.rsi})
                  {o.regime_note ? " · risk-off throttle applied" : ""}
                </div>
                <div className="muted" style={{ marginTop: 6, fontSize: 12 }}>
                  Playbook: <PlaybookBadge playbook={o.playbook} />
                  {o.playbook === "reversal" && (
                    <> · early turn —{o.reversal_detail.cross_up ? " 5/9 cross↑" : ""}
                      {o.reversal_detail.rsi_turning ? " · RSI off oversold" : ""}
                      {o.reversal_detail.reclaimed_50 ? " · reclaimed 50-MA" : ""}
                      {o.reversal_detail.reclaimed_200 ? " · reclaimed 200-MA" : ""}
                      {o.risk.atr_stop_mult ? ` · tighter ${o.risk.atr_stop_mult}×ATR stop` : ""}</>
                  )}
                  {o.playbooks?.length === 2 && <> · also qualifies for both setups</>}
                </div>
                <div style={{ marginTop: 10 }}>
                  <Sparkline spark={o.spark} width={280} height={72} />
                </div>
              </div>

              <div>
                <RewardRiskGauge risk={o.risk} />
                <button
                  className="btn primary sm"
                  style={{ marginTop: 10 }}
                  onClick={(e) => {
                    e.stopPropagation();
                    openBuy({ ticker: o.ticker, price: o.price, risk: o.risk, name: o.name });
                  }}
                >
                  ＋ Log Buy {o.ticker}
                </button>
              </div>

              <div>
                <div className="section-title">Catalyst &amp; trend</div>
                <ul style={{ margin: 0, paddingLeft: 16, fontSize: 13, lineHeight: 1.8 }}>
                  <li>Earnings: {o.catalyst_detail.earnings_date ?? "—"}
                    {o.catalyst_detail.days_to_earnings != null ? ` (${o.catalyst_detail.days_to_earnings}d)` : ""}
                    {o.catalyst_detail.earnings_soon ? " ⚠ soon" : ""}</li>
                  <li>Last EPS surprise: {o.catalyst_detail.last_surprise_pct != null
                    ? pct(o.catalyst_detail.last_surprise_pct * 100) : "—"}</li>
                  <li>Analyst trend: {o.catalyst_detail.rec_trend.toFixed(2)}</li>
                  <li>Above 50/200 MA: {o.trend_detail.above_fast_ma ? "✓" : "✗"} / {o.trend_detail.above_slow_ma ? "✓" : "✗"}
                    {o.trend_detail.slow_ma_rising ? " · 200 rising" : ""}</li>
                </ul>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

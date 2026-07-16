"use client";
// Unified Positions section: real + paper holdings logged from the UI (no
// positions.json). A filter (All / Real / Paper) drives the list and the stats.
// Exit signals are recomputed client-side from results.json data for any name in
// the latest scan (results.market covers every scored ticker, not just the shown
// opportunities); a holding outside the scan shows the trailing stop alone.
import { useMemo, useState } from "react";
import { money, pct, signedMoney, rMult } from "@/lib/format";
import {
  computeStats,
  currentPrice,
  exportJSON,
  isStale,
  stopGrade,
  type KindFilter,
  type PaperLot,
  type Quote,
} from "@/lib/paper";
import { computeExitSignals, type ExitGrade, type MarketData } from "@/lib/exitSignals";
import { statusClass } from "./badges";
import { usePaper } from "./PaperProvider";
import PaperStatsView from "./PaperStats";

const border = (c: string) =>
  `var(--${c === "green" ? "good" : c === "yellow" ? "warning" : c === "orange" ? "serious" : "critical"})`;

const SIGNAL_LABELS: { key: "trailing_stop" | "ema_cross" | "target" | "rsi"; label: string }[] = [
  { key: "trailing_stop", label: "Trailing Stop" },
  { key: "ema_cross", label: "EMA 20/50" },
  { key: "target", label: "Target" },
  { key: "rsi", label: "RSI" },
];

function ExitCard({ label, g }: { label: string; g: ExitGrade }) {
  return (
    <div style={{
      border: "1px solid var(--border)", borderLeft: `3px solid ${border(g.color)}`,
      borderRadius: 8, padding: "8px 10px", minWidth: 120, flex: 1,
    }}>
      <div className="muted" style={{ fontSize: 11 }}>{label}</div>
      <div className="row" style={{ gap: 6, marginTop: 2 }}>
        <span className={`dot ${g.color}`} />
        <span style={{ fontSize: 12, fontWeight: 600 }}>{g.label}</span>
      </div>
    </div>
  );
}

function marketData(lot: PaperLot, quotes: Record<string, Quote>): MarketData | undefined {
  const q = quotes[lot.ticker];
  if (!q || q.emaFast == null || q.emaSlow == null || q.atr == null || q.rsi == null) return undefined;
  return { price: currentPrice(lot, quotes), emaFast: q.emaFast, emaSlow: q.emaSlow, atr: q.atr, rsi: q.rsi };
}

function KindBadge({ kind }: { kind: "paper" | "real" }) {
  return kind === "real" ? (
    <span className="badge status-good" title="Real holding">💵 Real</span>
  ) : (
    <span className="badge watch" title="Paper (simulated)">📝 Paper</span>
  );
}

function PositionRow({ lot }: { lot: PaperLot }) {
  const { quotes, openSell, openEdit, sell } = usePaper();
  const [open, setOpen] = useState(false);
  const price = currentPrice(lot, quotes);
  const stale = isStale(lot, quotes);
  const mkt = lot.shares * price;
  const unreal = (price - lot.entryPrice) * lot.shares;
  const unrealPct = lot.entryPrice > 0 ? ((price - lot.entryPrice) / lot.entryPrice) * 100 : 0;
  const risk = lot.stop != null ? lot.entryPrice - lot.stop : null;
  const rNow = risk && risk > 0 ? (price - lot.entryPrice) / risk : null;

  const g0 = stopGrade(price, lot);
  const exit = computeExitSignals(marketData(lot, quotes), lot.entryPrice, lot.highWatermark, lot.trailPct);
  const urgency: ExitGrade = exit ? exit.urgency : { color: g0.color, label: g0.label };
  const hit = g0.color === "red";

  return (
    <>
      <tr
        className="rowbtn"
        onClick={() => setOpen((o) => !o)}
        style={hit ? { background: "color-mix(in srgb, var(--critical) 8%, transparent)" } : undefined}
      >
        <td className="l">
          <div className="row" style={{ gap: 6 }}>
            <span style={{ fontWeight: 650 }}>{lot.ticker} {open ? "▾" : "▸"}</span>
            <KindBadge kind={lot.kind} />
          </div>
          <div className="muted" style={{ fontSize: 11 }}>{lot.entryDate}{lot.note ? ` · ${lot.note}` : ""}</div>
        </td>
        <td className="tnum">{lot.shares}</td>
        <td className="tnum">{money(lot.entryPrice)}</td>
        <td className="tnum">
          {money(price)}{" "}
          {stale && <span className="badge status-warning" title="No price in the latest scan — last known mark">stale</span>}
        </td>
        <td className="tnum">{money(mkt)}</td>
        <td className={`tnum ${unreal >= 0 ? "pos" : "neg"}`}>
          {signedMoney(unreal)}<div style={{ fontSize: 11 }}>{unrealPct >= 0 ? "+" : ""}{unrealPct.toFixed(1)}%</div>
        </td>
        <td className="tnum">{rMult(rNow)}</td>
        <td className="l">
          <span className={`badge ${statusClass[urgency.color]}`}>{urgency.label}</span>
          <div className="muted tnum" style={{ fontSize: 11, marginTop: 2 }}>
            stop {money(g0.level)} · {g0.cushionPct >= 0 ? "+" : ""}{g0.cushionPct.toFixed(1)}%
          </div>
        </td>
        <td className="l" onClick={(e) => e.stopPropagation()}>
          <div className="row" style={{ gap: 6 }}>
            <button className="btn sm" onClick={() => openSell(lot.id)}>Sell</button>
            {hit && (
              <button className="btn sm danger" onClick={() => sell(lot.id, lot.shares, g0.level, "trailing_stop")}>
                @ stop
              </button>
            )}
            <button className="btn sm ghost" onClick={() => openEdit(lot.id)}>Edit</button>
          </div>
        </td>
      </tr>
      {open && (
        <tr className="detail">
          <td colSpan={9}>
            <div style={{ padding: "6px 4px 12px" }}>
              {exit ? (
                <div className="row" style={{ gap: 8, alignItems: "stretch" }}>
                  {SIGNAL_LABELS.map((s) => (
                    <ExitCard key={s.key} label={s.label} g={exit.signals[s.key]} />
                  ))}
                </div>
              ) : (
                <div className="row" style={{ gap: 8, alignItems: "stretch" }}>
                  <ExitCard label="Trailing Stop" g={{ color: g0.color, label: g0.label }} />
                  <div className="muted" style={{ fontSize: 12, alignSelf: "center" }}>
                    Full EMA / target / RSI signals cover any name in the latest scan. This
                    ticker is outside the current scan — showing the trailing stop only.
                  </div>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function OpenPositions({ lots }: { lots: PaperLot[] }) {
  if (!lots.length) {
    return (
      <div className="muted" style={{ fontSize: 13 }}>
        No open positions here. Click <b>Buy</b> above (tag it Paper or Real), or open an
        Opportunity below and hit <b>Log Buy</b>.
      </div>
    );
  }
  const rows = [...lots].sort((a, b) => a.ticker.localeCompare(b.ticker));
  return (
    <div style={{ overflowX: "auto" }}>
      <table className="tbl">
        <thead>
          <tr>
            <th className="l">Ticker</th><th>Shares</th><th>Entry</th><th>Current</th>
            <th>Mkt value</th><th>Unreal P&L</th><th>R now</th>
            <th className="l">Exit signal</th><th className="l">Actions</th>
          </tr>
        </thead>
        <tbody>{rows.map((lot) => <PositionRow key={lot.id} lot={lot} />)}</tbody>
      </table>
    </div>
  );
}

function ExportMenu() {
  const { account, openImport, openSettings } = usePaper();
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(exportJSON(account));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* blocked */ }
    setOpen(false);
  }
  function download() {
    const blob = new Blob([exportJSON(account)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "positions.json"; a.click();
    URL.revokeObjectURL(url);
    setOpen(false);
  }
  return (
    <div style={{ position: "relative" }}>
      <button className="btn" onClick={() => setOpen((o) => !o)}>{copied ? "✓ Copied" : "Export / More ▾"}</button>
      {open && (
        <>
          <div className="menu-backdrop" onClick={() => setOpen(false)} />
          <div className="menu">
            <button onClick={copy}>Copy JSON to clipboard</button>
            <button onClick={download}>Download JSON</button>
            <button onClick={() => { openImport(); setOpen(false); }}>Import…</button>
            <button onClick={() => { openSettings(); setOpen(false); }}>Account settings…</button>
          </div>
        </>
      )}
    </div>
  );
}

function ClosedLedger({ trades }: { trades: import("@/lib/paper").PaperTrade[] }) {
  if (!trades.length) return null;
  const rows = [...trades].sort((a, b) => b.exitDate.localeCompare(a.exitDate));
  return (
    <details style={{ marginTop: 14 }}>
      <summary style={{ cursor: "pointer", fontSize: 13 }} className="muted">
        Closed-trade ledger ({rows.length})
      </summary>
      <div style={{ overflowX: "auto", marginTop: 8 }}>
        <table className="tbl">
          <thead>
            <tr>
              <th className="l">Ticker</th><th>Shares</th><th>Entry</th><th>Exit</th>
              <th>P&L</th><th>%</th><th>R</th><th>Hold</th><th className="l">Reason</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.id}>
                <td className="l" style={{ fontWeight: 650 }}>
                  <span className="row" style={{ gap: 6 }}>{t.ticker} <KindBadge kind={t.kind} /></span>
                  <div className="muted" style={{ fontSize: 11 }}>{t.entryDate} → {t.exitDate}</div>
                </td>
                <td className="tnum">{t.shares}</td>
                <td className="tnum">{money(t.entryPrice)}</td>
                <td className="tnum">{money(t.exitPrice)}</td>
                <td className={`tnum ${t.pnlAbs >= 0 ? "pos" : "neg"}`}>{signedMoney(t.pnlAbs)}</td>
                <td className={`tnum ${t.pnlPct >= 0 ? "pos" : "neg"}`}>{pct(t.pnlPct)}</td>
                <td className="tnum">{rMult(t.rMultiple)}</td>
                <td className="tnum">{t.holdDays}d</td>
                <td className="l muted">{t.reason.replace("_", " ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

const FILTERS: { key: KindFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "real", label: "💵 Real" },
  { key: "paper", label: "📝 Paper" },
];

const pn = (n: number) => (n > 0 ? "var(--pos)" : n < 0 ? "var(--neg)" : undefined);

export default function PortfolioPanel() {
  const { account, quotes, mounted, openBuy } = usePaper();
  const [filter, setFilter] = useState<KindFilter>("all");

  const s = useMemo(() => computeStats(account, quotes, filter), [account, quotes, filter]);

  if (!mounted) {
    return (
      <div className="card">
        <div className="section-title">Positions</div>
        <div className="muted">Loading account…</div>
      </div>
    );
  }

  const lots = account.lots.filter((l) => filter === "all" || l.kind === filter);
  const trades = account.trades.filter((t) => filter === "all" || t.kind === filter);

  // Summary tiles adapt to the filter: paper shows the simulated account,
  // real/all show a holdings P&L view.
  const tiles =
    filter === "paper"
      ? [
          { k: "Equity", v: money(s.equity) },
          { k: "Cash", v: money(s.cash) },
          { k: "Invested", v: money(s.invested), sub: `${s.openCount} open` },
          { k: "Unrealized", v: signedMoney(s.unrealized), color: pn(s.unrealized) },
          { k: "Total P&L", v: signedMoney(s.totalPnl), color: pn(s.totalPnl), sub: `${s.totalReturnPct >= 0 ? "+" : ""}${s.totalReturnPct.toFixed(1)}% vs ${money(account.startingCapital)}` },
        ]
      : [
          { k: "Cost basis", v: money(s.invested), sub: `${s.openCount} open` },
          { k: "Market value", v: money(s.marketValue) },
          { k: "Unrealized", v: signedMoney(s.unrealized), color: pn(s.unrealized) },
          { k: "Realized", v: signedMoney(s.totalRealized), color: pn(s.totalRealized) },
          { k: "Total P&L", v: signedMoney(s.realizedPlusUnrealized), color: pn(s.realizedPlusUnrealized), sub: filter === "all" ? `incl. paper cash ${money(s.cash)}` : undefined },
        ];

  return (
    <div className="card">
      <div className="row spread" style={{ marginBottom: 12 }}>
        <div>
          <h2 style={{ fontSize: 16 }}>Positions</h2>
          <div className="muted" style={{ fontSize: 12 }}>
            Real + paper in one place · {account.stopMode === "auto" ? "auto-close" : "alert"} trailing stops · saved in this browser
          </div>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn primary" onClick={() => openBuy()}>＋ Buy</button>
          <ExportMenu />
        </div>
      </div>

      <div className="segmented" style={{ marginBottom: 14, maxWidth: 320 }}>
        {FILTERS.map((f) => (
          <button key={f.key} className={filter === f.key ? "on" : ""} onClick={() => setFilter(f.key)}>
            {f.label}
          </button>
        ))}
      </div>

      <div className="tiles" style={{ marginBottom: 16 }}>
        {tiles.map((t) => (
          <div className="tile" key={t.k}>
            <div className="v tnum" style={{ color: t.color, fontSize: 22 }}>{t.v}</div>
            <div className="k">{t.k}</div>
            {t.sub && <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>{t.sub}</div>}
          </div>
        ))}
      </div>

      <div className="section-title">Open positions <span className="muted">· click a row for exit signals</span></div>
      <OpenPositions lots={lots} />

      <div className="section-title" style={{ marginTop: 18 }}>Statistics (closed trades)</div>
      <PaperStatsView s={s} />

      <ClosedLedger trades={trades} />

      <div className="muted" style={{ fontSize: 11, marginTop: 14, lineHeight: 1.6 }}>
        Log buys/sells here and tag them <b>Paper</b> (simulated cash) or <b>Real</b> (your actual
        book) — no more editing <code>positions.json</code>. Prices mark against the engine&apos;s
        latest scan (end-of-day); tickers not in the scan show <b>stale</b> and only the trailing
        stop. State is per-browser — use <b>Export</b> to back it up or share it. Decision-support
        only; no real orders.
      </div>
    </div>
  );
}

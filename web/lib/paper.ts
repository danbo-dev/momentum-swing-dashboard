"use client";
// Client-side paper-trading account, persisted to localStorage. The deployed
// dashboard is a read-only static site, so all trade state lives in the browser
// and is moved around via Export/Import. Prices are marked against whatever the
// engine last wrote into results.json (passed in as `quotes`).
import { useCallback, useEffect, useState } from "react";

export const STORAGE_KEY = "msd_paper_v1";
export const DEFAULT_STARTING_CAPITAL = 100_000;
/** Mirrors engine config.yaml -> risk.trailing_stop_pct so paper lots and the
 *  engine's "Tracked Positions" grade the trailing stop identically. */
export const DEFAULT_TRAIL_PCT = 10.0;

export type StopMode = "alert" | "auto";
export type SellReason = "target" | "stop" | "trailing_stop" | "signal" | "manual";
/** Paper = simulated account (with cash); real = a log of actual holdings (no cash). */
export type Kind = "paper" | "real";
export type KindFilter = Kind | "all";

export interface RiskBlock {
  entry: number;
  stop: number;
  target: number;
  risk_per_share: number;
  reward_risk: number;
  suggested_shares: number;
  suggested_dollars: number;
}

/** Compact per-ticker quote derived server-side from results.json. The optional
 *  ema/atr/rsi carry enough to recompute the engine's 4-signal exit grade. */
export interface Quote {
  ticker: string;
  price: number;
  name?: string;
  sector?: string;
  risk?: RiskBlock;
  emaFast?: number;
  emaSlow?: number;
  atr?: number;
  rsi?: number;
}

export interface PaperLot {
  id: string;
  ticker: string;
  kind: Kind;
  shares: number;
  entryPrice: number;
  entryDate: string; // yyyy-mm-dd
  highWatermark: number; // ratchets up on every mark
  trailPct: number;
  stop?: number; // initial hard stop, for R-multiple
  target?: number;
  lastMark?: number; // last observed price (for stale display)
  note?: string;
}

export interface PaperTrade {
  id: string;
  ticker: string;
  kind: Kind;
  shares: number;
  entryPrice: number;
  entryDate: string;
  exitPrice: number;
  exitDate: string;
  stop?: number;
  target?: number;
  trailPct: number;
  pnlAbs: number;
  pnlPct: number;
  rMultiple?: number;
  holdDays: number;
  reason: SellReason;
}

export interface PaperAccount {
  version: number;
  startingCapital: number; // paper simulated account
  cash: number; // paper buying power (real positions don't use cash)
  stopMode: StopMode;
  defaultTrailPct: number;
  lastKind: Kind; // default for the next Buy dialog
  migratedReal: boolean; // positions.json seed already imported once
  lots: PaperLot[];
  trades: PaperTrade[];
}

export function emptyAccount(
  startingCapital = DEFAULT_STARTING_CAPITAL,
  defaultTrailPct = DEFAULT_TRAIL_PCT,
  stopMode: StopMode = "alert",
): PaperAccount {
  return {
    version: 2,
    startingCapital,
    cash: startingCapital,
    stopMode,
    defaultTrailPct,
    lastKind: "paper",
    migratedReal: false,
    lots: [],
    trades: [],
  };
}

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

function genId(): string {
  try {
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  } catch {
    /* ignore */
  }
  return `id-${Date.now()}-${Math.round(Math.random() * 1e9)}`;
}

export function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function daysBetween(a: string, b: string): number {
  const ms = new Date(b).getTime() - new Date(a).getTime();
  return Math.max(0, Math.round(ms / 86_400_000));
}

/** Trailing-stop level off the high-water mark (matches engine positions.py). */
export function stopLevel(lot: Pick<PaperLot, "highWatermark" | "trailPct">): number {
  return lot.highWatermark * (1 - lot.trailPct / 100);
}

export type StopColor = "green" | "yellow" | "orange" | "red";

/** Same traffic-light thresholds the engine uses for the trailing stop. */
export function stopGrade(price: number, lot: Pick<PaperLot, "highWatermark" | "trailPct">): {
  color: StopColor;
  label: string;
  level: number;
  cushionPct: number;
} {
  const level = stopLevel(lot);
  const cushion = price > 0 ? ((price - level) / price) * 100 : 0;
  let color: StopColor;
  let label: string;
  if (price <= level) {
    color = "red";
    label = "STOP HIT";
  } else if (cushion < 3) {
    color = "orange";
    label = "Near stop";
  } else if (cushion < 7) {
    color = "yellow";
    label = "Watch stop";
  } else {
    color = "green";
    label = "Healthy cushion";
  }
  return { color, label, level, cushionPct: cushion };
}

/** Best-known current price for a lot: fresh quote, else last mark, else entry. */
export function currentPrice(lot: PaperLot, quotes: Record<string, Quote>): number {
  return quotes[lot.ticker]?.price ?? lot.lastMark ?? lot.entryPrice;
}

export function isStale(lot: PaperLot, quotes: Record<string, Quote>): boolean {
  return !quotes[lot.ticker];
}

function realizedTrade(
  lot: PaperLot,
  shares: number,
  exitPrice: number,
  exitDate: string,
  reason: SellReason,
): PaperTrade {
  const pnlAbs = (exitPrice - lot.entryPrice) * shares;
  const pnlPct = ((exitPrice - lot.entryPrice) / lot.entryPrice) * 100;
  const risk = lot.stop != null ? lot.entryPrice - lot.stop : null;
  const rMultiple = risk && risk > 0 ? (exitPrice - lot.entryPrice) / risk : undefined;
  return {
    id: genId(),
    ticker: lot.ticker,
    kind: lot.kind,
    shares,
    entryPrice: lot.entryPrice,
    entryDate: lot.entryDate,
    exitPrice,
    exitDate,
    stop: lot.stop,
    target: lot.target,
    trailPct: lot.trailPct,
    pnlAbs,
    pnlPct,
    rMultiple,
    holdDays: daysBetween(lot.entryDate, exitDate),
    reason,
  };
}

export interface BuyInput {
  ticker: string;
  kind: Kind;
  shares: number;
  price: number;
  stop?: number;
  target?: number;
  trailPct?: number;
  note?: string;
  date?: string;
}

// ---------------------------------------------------------------------------
// Pure reducers (account in -> account out)
// ---------------------------------------------------------------------------

export function applyBuy(acc: PaperAccount, input: BuyInput): PaperAccount {
  const shares = input.shares;
  const price = input.price;
  const lot: PaperLot = {
    id: genId(),
    ticker: input.ticker.toUpperCase().trim(),
    kind: input.kind,
    shares,
    entryPrice: price,
    entryDate: input.date || todayISO(),
    highWatermark: Math.max(price, input.stop ?? 0),
    trailPct: input.trailPct ?? acc.defaultTrailPct,
    stop: input.stop,
    target: input.target,
    lastMark: price,
    note: input.note,
  };
  // Only the paper simulated account has cash buying power.
  const cash = input.kind === "paper" ? acc.cash - shares * price : acc.cash;
  return { ...acc, cash, lastKind: input.kind, lots: [...acc.lots, lot] };
}

export function applySell(
  acc: PaperAccount,
  lotId: string,
  sharesReq: number,
  price: number,
  reason: SellReason,
  date = todayISO(),
): PaperAccount {
  const lot = acc.lots.find((l) => l.id === lotId);
  if (!lot) return acc;
  const shares = Math.min(sharesReq, lot.shares);
  if (shares <= 0) return acc;
  const trade = realizedTrade(lot, shares, price, date, reason);
  const remaining = lot.shares - shares;
  const lots =
    remaining > 1e-9
      ? acc.lots.map((l) => (l.id === lotId ? { ...l, shares: remaining } : l))
      : acc.lots.filter((l) => l.id !== lotId);
  const cash = lot.kind === "paper" ? acc.cash + shares * price : acc.cash;
  return { ...acc, cash, lots, trades: [...acc.trades, trade] };
}

export type LotPatch = Partial<
  Pick<PaperLot, "shares" | "entryPrice" | "stop" | "target" | "trailPct" | "note" | "highWatermark">
>;

export function applyEditLot(acc: PaperAccount, lotId: string, patch: LotPatch): PaperAccount {
  const lot = acc.lots.find((l) => l.id === lotId);
  if (!lot) return acc;
  const next: PaperLot = { ...lot, ...patch };
  next.highWatermark = Math.max(next.highWatermark, next.entryPrice);
  // keep paper equity consistent: refund old cost basis, charge new (paper only)
  const cashDelta =
    lot.kind === "paper" ? lot.shares * lot.entryPrice - next.shares * next.entryPrice : 0;
  return {
    ...acc,
    cash: acc.cash + cashDelta,
    lots: acc.lots.map((l) => (l.id === lotId ? next : l)),
  };
}

/** Ratchet high-water marks and record last marks. In auto stop-mode, close any
 *  lot whose mark has breached its trailing stop. Returns null if nothing changed. */
export function applyMarks(
  acc: PaperAccount,
  quotes: Record<string, Quote>,
  date = todayISO(),
): PaperAccount | null {
  let changed = false;
  let cash = acc.cash;
  const lots: PaperLot[] = [];
  const closed: PaperTrade[] = [];
  for (const lot of acc.lots) {
    const q = quotes[lot.ticker];
    if (!q) {
      lots.push(lot);
      continue;
    }
    const price = q.price;
    const hwm = Math.max(lot.highWatermark, price);
    const marked: PaperLot = { ...lot, highWatermark: hwm, lastMark: price };
    if (hwm !== lot.highWatermark || price !== lot.lastMark) changed = true;
    if (acc.stopMode === "auto") {
      const level = stopLevel(marked);
      if (price <= level) {
        closed.push(realizedTrade(marked, marked.shares, level, date, "trailing_stop"));
        if (marked.kind === "paper") cash += marked.shares * level;
        changed = true;
        continue; // lot fully closed
      }
    }
    lots.push(marked);
  }
  if (!changed) return null;
  return { ...acc, cash, lots, trades: closed.length ? [...acc.trades, ...closed] : acc.trades };
}

export function applyStartingCapital(acc: PaperAccount, value: number): PaperAccount {
  return { ...acc, cash: acc.cash + (value - acc.startingCapital), startingCapital: value };
}

/** One position from the engine's positions.json (via results.json r.positions). */
export interface RealSeed {
  ticker: string;
  entry_price: number;
  shares: number;
  entry_date?: string;
  high_watermark?: number;
}

/** Import the engine's held positions as Real lots — once. No-op if already done. */
export function applyMigrateRealSeed(
  acc: PaperAccount,
  seed: RealSeed[],
  defaultTrailPct = acc.defaultTrailPct,
): PaperAccount {
  if (acc.migratedReal) return acc;
  const lots: PaperLot[] = seed
    .filter((s) => s.ticker && s.entry_price > 0 && s.shares > 0)
    .map((s) => ({
      id: genId(),
      ticker: s.ticker.toUpperCase().trim(),
      kind: "real" as const,
      shares: s.shares,
      entryPrice: s.entry_price,
      entryDate: s.entry_date || todayISO(),
      highWatermark: Math.max(s.high_watermark ?? 0, s.entry_price),
      trailPct: defaultTrailPct,
      lastMark: s.entry_price,
    }));
  return { ...acc, migratedReal: true, lots: [...acc.lots, ...lots] };
}

// ---------------------------------------------------------------------------
// Statistics
// ---------------------------------------------------------------------------

export interface PaperStats {
  // realized (closed trades)
  closedCount: number;
  wins: number;
  losses: number;
  winRatePct: number;
  avgWinPct: number;
  avgLossPct: number;
  avgR: number | null;
  expectancyR: number | null;
  profitFactor: number | null;
  totalRealized: number;
  avgHoldDays: number;
  bestPct: number | null;
  worstPct: number | null;
  maxDrawdownPct: number;
  // open (filtered by kind)
  openCount: number;
  invested: number;
  marketValue: number;
  unrealized: number;
  unrealizedPct: number;
  realizedPlusUnrealized: number; // kind-agnostic P&L = totalRealized + unrealized
  // paper simulated account (always the paper book, regardless of filter)
  cash: number;
  equity: number;
  totalPnl: number;
  totalReturnPct: number;
}

function mean(xs: number[]): number {
  return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0;
}

export function computeStats(
  acc: PaperAccount,
  quotes: Record<string, Quote>,
  kind: KindFilter = "all",
): PaperStats {
  const inFilter = <T extends { kind: Kind }>(x: T) => kind === "all" || x.kind === kind;
  const closed = acc.trades.filter(inFilter);
  const openLots = acc.lots.filter(inFilter);
  const winsArr = closed.filter((t) => t.pnlAbs > 0);
  const lossArr = closed.filter((t) => t.pnlAbs <= 0);
  const rvals = closed.map((t) => t.rMultiple).filter((r): r is number => r != null);
  const winR = rvals.filter((r) => r > 0);
  const lossR = rvals.filter((r) => r <= 0);
  const grossProfit = winsArr.reduce((a, t) => a + t.pnlAbs, 0);
  const grossLoss = Math.abs(lossArr.reduce((a, t) => a + t.pnlAbs, 0));

  // realized equity curve -> max drawdown
  const byExit = [...closed].sort((a, b) => a.exitDate.localeCompare(b.exitDate));
  let eq = acc.startingCapital;
  let peak = eq;
  let maxDD = 0;
  for (const t of byExit) {
    eq += t.pnlAbs;
    peak = Math.max(peak, eq);
    if (peak > 0) maxDD = Math.max(maxDD, ((peak - eq) / peak) * 100);
  }

  const invested = openLots.reduce((a, l) => a + l.shares * l.entryPrice, 0);
  const marketValue = openLots.reduce((a, l) => a + l.shares * currentPrice(l, quotes), 0);
  const unrealized = marketValue - invested;
  const totalRealized = closed.reduce((a, t) => a + t.pnlAbs, 0);

  // paper simulated account (always the paper book: cash + paper open value)
  const paperMV = acc.lots
    .filter((l) => l.kind === "paper")
    .reduce((a, l) => a + l.shares * currentPrice(l, quotes), 0);
  const equity = acc.cash + paperMV;
  const totalPnl = equity - acc.startingCapital;

  const winRate = closed.length ? (winsArr.length / closed.length) * 100 : 0;
  const avgWinR = winR.length ? mean(winR) : 0;
  const avgLossR = lossR.length ? mean(lossR) : 0;
  const expectancyR =
    rvals.length ? (winRate / 100) * avgWinR + (1 - winRate / 100) * avgLossR : null;

  return {
    closedCount: closed.length,
    wins: winsArr.length,
    losses: lossArr.length,
    winRatePct: winRate,
    avgWinPct: winsArr.length ? mean(winsArr.map((t) => t.pnlPct)) : 0,
    avgLossPct: lossArr.length ? mean(lossArr.map((t) => t.pnlPct)) : 0,
    avgR: rvals.length ? mean(rvals) : null,
    expectancyR,
    profitFactor: grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? Infinity : null,
    totalRealized,
    avgHoldDays: closed.length ? mean(closed.map((t) => t.holdDays)) : 0,
    bestPct: closed.length ? Math.max(...closed.map((t) => t.pnlPct)) : null,
    worstPct: closed.length ? Math.min(...closed.map((t) => t.pnlPct)) : null,
    maxDrawdownPct: maxDD,
    openCount: openLots.length,
    invested,
    marketValue,
    unrealized,
    unrealizedPct: invested > 0 ? (unrealized / invested) * 100 : 0,
    realizedPlusUnrealized: totalRealized + unrealized,
    cash: acc.cash,
    equity,
    totalPnl,
    totalReturnPct: acc.startingCapital > 0 ? (totalPnl / acc.startingCapital) * 100 : 0,
  };
}

// ---------------------------------------------------------------------------
// Import / export
// ---------------------------------------------------------------------------

export function exportJSON(acc: PaperAccount): string {
  return JSON.stringify(acc, null, 2);
}

export function parseImport(text: string): PaperAccount {
  const raw = JSON.parse(text);
  if (!raw || typeof raw !== "object" || !Array.isArray(raw.lots) || !Array.isArray(raw.trades)) {
    throw new Error("Not a valid paper-trading export (missing lots/trades).");
  }
  // v1 -> v2: entries had no `kind`; treat everything logged before as paper.
  const withKind = <T extends { kind?: Kind }>(x: T): T & { kind: Kind } => ({
    ...x,
    kind: x.kind === "real" ? "real" : "paper",
  });
  return {
    version: 2,
    startingCapital: Number(raw.startingCapital) || DEFAULT_STARTING_CAPITAL,
    cash: Number(raw.cash) || 0,
    stopMode: raw.stopMode === "auto" ? "auto" : "alert",
    defaultTrailPct: Number(raw.defaultTrailPct) || DEFAULT_TRAIL_PCT,
    lastKind: raw.lastKind === "real" ? "real" : "paper",
    // v1 imports predate the real-seed migration, so allow it to run once.
    migratedReal: Boolean(raw.migratedReal),
    lots: raw.lots.map(withKind),
    trades: raw.trades.map(withKind),
  };
}

// ---------------------------------------------------------------------------
// React hook — localStorage-backed account
// ---------------------------------------------------------------------------

export interface PaperApi {
  account: PaperAccount;
  mounted: boolean;
  buy: (input: BuyInput) => void;
  sell: (lotId: string, shares: number, price: number, reason: SellReason) => void;
  editLot: (lotId: string, patch: LotPatch) => void;
  mark: (quotes: Record<string, Quote>) => void;
  migrateRealSeed: (seed: RealSeed[]) => void;
  setStartingCapital: (v: number) => void;
  setDefaultTrailPct: (v: number) => void;
  setStopMode: (m: StopMode) => void;
  reset: () => void;
  importText: (text: string) => void;
}

export function usePaperAccount(): PaperApi {
  const [account, setAccount] = useState<PaperAccount>(() => emptyAccount());
  const [mounted, setMounted] = useState(false);

  // Load once on mount (client only) to avoid SSR hydration mismatch.
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setAccount(parseImport(raw));
    } catch {
      /* corrupt/legacy — start fresh */
    }
    setMounted(true);
  }, []);

  // Persist after every change. Guard on `mounted` (state, false on the first
  // render) so the hydration pass never writes the empty default over the value
  // we just loaded from localStorage.
  useEffect(() => {
    if (!mounted) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(account));
    } catch {
      /* quota/full — ignore */
    }
  }, [account, mounted]);

  const buy = useCallback((input: BuyInput) => setAccount((a) => applyBuy(a, input)), []);
  const sell = useCallback(
    (lotId: string, shares: number, price: number, reason: SellReason) =>
      setAccount((a) => applySell(a, lotId, shares, price, reason)),
    [],
  );
  const editLot = useCallback(
    (lotId: string, patch: LotPatch) => setAccount((a) => applyEditLot(a, lotId, patch)),
    [],
  );
  const mark = useCallback(
    (quotes: Record<string, Quote>) =>
      setAccount((a) => {
        const next = applyMarks(a, quotes);
        return next ?? a;
      }),
    [],
  );
  const migrateRealSeed = useCallback(
    (seed: RealSeed[]) =>
      setAccount((a) => {
        const next = applyMigrateRealSeed(a, seed);
        return next === a ? a : next;
      }),
    [],
  );
  const setStartingCapital = useCallback(
    (v: number) => setAccount((a) => applyStartingCapital(a, v)),
    [],
  );
  const setDefaultTrailPct = useCallback(
    (v: number) => setAccount((a) => ({ ...a, defaultTrailPct: v })),
    [],
  );
  const setStopMode = useCallback((m: StopMode) => setAccount((a) => ({ ...a, stopMode: m })), []);
  const reset = useCallback(
    () =>
      setAccount((a) => ({
        ...emptyAccount(a.startingCapital, a.defaultTrailPct, a.stopMode),
        // don't re-import the engine seed after an explicit reset
        migratedReal: true,
        lastKind: a.lastKind,
      })),
    [],
  );
  const importText = useCallback((text: string) => setAccount(parseImport(text)), []);

  return {
    account,
    mounted,
    buy,
    sell,
    editLot,
    mark,
    migrateRealSeed,
    setStartingCapital,
    setDefaultTrailPct,
    setStopMode,
    reset,
    importText,
  };
}

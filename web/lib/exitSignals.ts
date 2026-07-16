// Client-side port of engine/strategy/positions.py::exit_signals so held
// positions (real or paper) get the same 4-signal exit grading the engine's
// "Tracked Positions" panel used to show — computed from data already present in
// results.json (last EMA fast/slow, ATR, RSI, price). Thresholds and the reds>=2
// -> SELL urgency rollup match the engine exactly. Constants mirror config.yaml.
import { stopGrade, type StopColor } from "./paper";

export const ATR_STOP_MULT = 2.0; // config.yaml risk.atr_stop_mult
export const TARGET_R = 3.0; // config.yaml risk.target_r_multiple

export interface ExitGrade {
  color: StopColor;
  label: string;
  [k: string]: unknown;
}

/** Last-value market data for a ticker, sourced from results.json opportunities. */
export interface MarketData {
  price: number;
  emaFast: number;
  emaSlow: number;
  atr: number;
  rsi: number;
}

export interface ExitReport {
  price: number;
  pnlPct: number;
  urgency: ExitGrade;
  signals: {
    trailing_stop: ExitGrade;
    ema_cross: ExitGrade;
    target: ExitGrade;
    rsi: ExitGrade;
  };
}

const g = (color: StopColor, label: string, extra: Record<string, unknown> = {}): ExitGrade => ({
  color,
  label,
  ...extra,
});

/** Full 4-signal exit grade. Returns null unless enough market data is present. */
export function computeExitSignals(
  md: MarketData | undefined,
  entryPrice: number,
  highWatermark: number,
  trailPct: number,
): ExitReport | null {
  if (!md || !Number.isFinite(md.price)) return null;
  const price = md.price;

  // 1) trailing stop off the high-water mark (same math as lib/paper stopGrade)
  const ts0 = stopGrade(price, { highWatermark, trailPct });
  const trailing_stop = g(ts0.color, ts0.label, {
    cushion_pct: Number(ts0.cushionPct.toFixed(2)),
    level: Number(ts0.level.toFixed(2)),
  });

  // 2) EMA cross exit (fast crossing below slow)
  const gap = md.emaSlow !== 0 ? ((md.emaFast - md.emaSlow) / md.emaSlow) * 100 : 0;
  let ema_cross: ExitGrade;
  if (gap < 0) ema_cross = g("red", "Bearish cross");
  else if (gap < 1) ema_cross = g("orange", "Cross imminent");
  else if (gap < 3) ema_cross = g("yellow", "Gap narrowing");
  else ema_cross = g("green", "Healthy gap");
  ema_cross.gap_pct = Number(gap.toFixed(2));

  // 3) profit target (R-multiple from entry)
  const stop0 = entryPrice - ATR_STOP_MULT * md.atr;
  const target = entryPrice + TARGET_R * Math.max(entryPrice - stop0, 1e-9);
  const prog = (price - entryPrice) / Math.max(target - entryPrice, 1e-9);
  let tgt: ExitGrade;
  if (price >= target) tgt = g("red", "Target hit — take profits");
  else if (prog > 0.7) tgt = g("orange", "Approaching target");
  else if (prog > 0.3) tgt = g("yellow", "In progress");
  else tgt = g("green", "Room to run");
  tgt.progress_pct = Number((prog * 100).toFixed(1));
  tgt.target = Number(target.toFixed(2));

  // 4) RSI overbought
  const rv = md.rsi;
  let rsi_sig: ExitGrade;
  if (rv >= 80) rsi_sig = g("red", "Very overbought");
  else if (rv >= 70) rsi_sig = g("orange", "Overbought");
  else if (rv >= 60) rsi_sig = g("yellow", "Elevated");
  else rsi_sig = g("green", "Neutral");
  rsi_sig.rsi = Number(rv.toFixed(1));

  const signals = { trailing_stop, ema_cross, target: tgt, rsi: rsi_sig };
  const reds = Object.values(signals).filter((s) => s.color === "red").length;
  const oranges = Object.values(signals).filter((s) => s.color === "orange").length;
  let urgency: ExitGrade;
  if (reds >= 2) urgency = g("red", "SELL");
  else if (reds === 1 || oranges >= 2) urgency = g("orange", "Consider selling");
  else if (oranges === 1) urgency = g("yellow", "Watch closely");
  else urgency = g("green", "Hold");

  return {
    price: Number(price.toFixed(2)),
    pnlPct: Number((((price - entryPrice) / entryPrice) * 100).toFixed(2)),
    urgency,
    signals,
  };
}

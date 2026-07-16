// Types mirroring the engine's results.json / backtest.json contract.

export type Bucket = "strong_buy" | "watch" | "none";

export interface Spark {
  dates: string[];
  close: number[];
  ema_fast: number[];
  ema_slow: number[];
  volume: number[];
}

export interface RiskBlock {
  entry: number;
  atr: number;
  atr_stop_mult?: number;
  stop: number;
  target: number;
  risk_per_share: number;
  reward_risk: number;
  stop_pct: number;
  target_pct: number;
  suggested_shares: number;
  suggested_dollars: number;
}

export interface CatalystDetail {
  earnings_date: string | null;
  days_to_earnings: number | null;
  earnings_soon: boolean;
  last_surprise_pct: number | null;
  rec_trend: number;
}

export interface TriggerDetail {
  state: string;
  recent_cross: boolean;
  pullback: boolean;
  rsi: number;
  rsi_ok: boolean;
  passed: boolean;
}

export interface TrendDetail {
  above_fast_ma: boolean;
  above_slow_ma: boolean;
  fast_above_slow: boolean;
  slow_ma_rising: boolean;
  ma_fast: number;
  ma_slow: number;
}

export type Playbook = "continuation" | "reversal";

export interface ReversalDetail {
  state: string;          // "reversal" | "forming" | "none"
  cross_up: boolean;      // fast 5/9 EMA cross up
  rsi_turning: boolean;   // RSI lifting off oversold
  reclaimed_50: boolean;  // price reclaimed the 50-MA from below
  reclaimed_200: boolean; // flag: reclaimed the 200-MA from below
  rsi: number;
  passed: boolean;
}

export type FactorKey = "momentum" | "trend" | "catalyst" | "trigger";

export interface Opportunity {
  ticker: string;
  name: string;
  sector: string;
  price: number;
  score: number;
  bucket: Bucket;
  confirmed: boolean;
  regime_note: string | null;
  momentum_percentile: number;
  sub_scores: Record<FactorKey, number>;
  contributions: Record<FactorKey, number>;
  trend_detail: TrendDetail;
  catalyst_detail: CatalystDetail;
  trigger_detail: TriggerDetail;
  reversal_detail: ReversalDetail;
  playbook: Playbook | null;      // primary tag (continuation preferred)
  playbooks: Playbook[];          // every setup this name qualifies for
  continuation_score: number;
  reversal_score: number;
  risk: RiskBlock;
  reward_risk: number;
  rsi: number;
  change_1d: number;
  change_5d: number;
  change_21d: number;
  spark: Spark;
}

export interface MarketRegime {
  risk_on: boolean;
  benchmark: string;
  price: number;
  ma: number;
  ma_rising: boolean;
  label: string;
}

export interface Breadth {
  n: number;
  pct_above_slow_ma: number;
  pct_uptrend: number;
  pct_advancing: number;
  avg_rsi: number;
}

export interface UniverseStats {
  considered: number;
  passed_liquidity: number;
  passed_quality: number;
  dropped: Record<string, number>;
  quality_dropped: number;
  /** Broad-universe funnel cardinalities; null when running the seed list. */
  funnel?: FunnelStats | null;
}

export interface FunnelStats {
  base: number;              // Stage 0: type/exchange/name-filtered base list
  grouped_names: number;     // names seen in the grouped-daily screen frame
  screened: number;          // Stage 1: passed price / liquidity / history screen
  bucket: number;            // Stage 2: momentum-ranked deep-dive bucket
  momentum_pct_floor: number | null;  // excess-return floor of the bucket (%)
  capped_by_max_bucket: boolean;      // true if max_bucket raised the floor
}

export interface Position {
  ticker: string;
  entry_price: number;
  shares: number;
  entry_date?: string;
  exit?: PositionExit;
}

export interface ExitGrade {
  color: "green" | "yellow" | "orange" | "red";
  label: string;
  [k: string]: unknown;
}

export interface PositionExit {
  price: number;
  pnl_pct: number;
  urgency: ExitGrade;
  signals: {
    trailing_stop: ExitGrade;
    ema_cross: ExitGrade;
    target: ExitGrade;
    rsi: ExitGrade;
  };
}

export interface Results {
  schema_version: number;
  generated_at: string;
  providers: { price: string; fundamental: string };
  strategy: { name: string; horizon: string; factor_weights: Record<string, number> };
  market_regime: MarketRegime;
  breadth: Breadth;
  universe: UniverseStats;
  buckets: { strong_buy: number; watch: number };
  opportunities: Opportunity[];
  /** Last-value indicators for every scored name (not just opportunities) so the
   *  UI can grade exits for any scanned holding. Keyed by ticker. */
  market?: Record<string, MarketRow>;
  snapshot: SnapshotItem[];
  positions: Position[];
}

export interface MarketRow {
  price: number;
  ema_fast: number;
  ema_slow: number;
  atr: number;
  rsi: number;
}

export interface SnapshotItem {
  ticker: string;
  sector: string;
  score: number;
  change_21d: number;
  change_5d: number;
  bucket: Bucket;
  playbook?: Playbook | null;
}

export interface BacktestQuantile {
  quantile: number;
  avg_fwd_ret_pct: number;
  win_rate_pct: number;
  n: number;
}

export interface Backtest {
  error?: string;
  params?: Record<string, number>;
  provider?: string;
  n_observations?: number;
  quantiles?: BacktestQuantile[];
  long_short_spread_pct?: number;
  mean_rank_ic?: number;
  top_quantile_equity_curve?: { date: string; equity: number }[];
  verdict?: string;
}

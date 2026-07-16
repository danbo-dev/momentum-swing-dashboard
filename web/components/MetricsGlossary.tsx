// Expandable reference at the bottom of the dashboard: the strategy in plain
// English plus a definition for every metric on the page, including the
// paper-trading statistics. Static content (server component).

function Def({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <b>{term}</b> — <span className="sec2">{children}</span>
    </div>
  );
}

function Group({ title, children, open = false }: { title: string; children: React.ReactNode; open?: boolean }) {
  return (
    <details open={open} style={{ borderTop: "1px solid var(--grid)", padding: "10px 0" }}>
      <summary style={{ cursor: "pointer", fontWeight: 650, fontSize: 14 }}>{title}</summary>
      <div style={{ marginTop: 10, fontSize: 13, lineHeight: 1.55 }}>{children}</div>
    </details>
  );
}

export default function MetricsGlossary({ weights }: { weights?: Record<string, number> }) {
  const w = weights ?? {};
  const wtxt = (k: string) => (w[k] != null ? ` (weight ${w[k]})` : "");
  return (
    <details className="card" style={{ padding: "14px 16px" }}>
      <summary style={{ cursor: "pointer", fontWeight: 650, fontSize: 15 }}>
        📖 Definitions &amp; Strategy — reference
      </summary>
      <div style={{ marginTop: 6 }}>
        <p className="sec2" style={{ fontSize: 13, lineHeight: 1.6 }}>
          A screen for <b>multi-week to ~1-month swing trades</b>: rank US names by momentum and
          catalysts behind a quality/liquidity gate, size by volatility, and surface the buy/sell
          story. Decision-support only — no orders are placed. All parameters live in{" "}
          <code>engine/config.yaml</code>.
        </p>

        <Group title="Strategy — how names are chosen" open>
          <Def term="Gates (hard filters)">
            Liquidity (minimum price / dollar-volume) and a light quality screen. Junk and illiquid
            names never reach scoring.
          </Def>
          <Def term={`Momentum${wtxt("momentum")}`}>
            Primary factor. Blended 3/6/12-month <i>excess</i> return vs SPY, ranked cross-sectionally,
            plus 52-week-high proximity. This is the engine&apos;s core edge.
          </Def>
          <Def term={`Trend${wtxt("trend")}`}>
            Rewards price above rising 50/200-day moving averages — buy strength, not weakness.
          </Def>
          <Def term={`Catalyst${wtxt("catalyst")}`}>
            Post-earnings drift + improving analyst consensus. Imminent earnings are flagged and
            damped (event risk over a swing hold), not rewarded.
          </Def>
          <Def term={`Trigger${wtxt("trigger")}`}>
            The timing entry — the better of the two entry playbooks below.
          </Def>
          <Def term="Continuation (playbook)">
            Established-uptrend entry: a 20/50 EMA cross or a pullback to the rising 20-EMA with
            RSI inside a healthy band, above rising 50/200-day MAs. Wider 2×ATR stop.
          </Def>
          <Def term="Reversal (playbook)">
            Early-turn entry, caught <i>before</i> a continuation confirms: a fast 5/9 EMA cross up
            + RSI lifting off oversold (~35) + price reclaiming the 50-MA from below (a 200-MA
            reclaim is flagged as a bigger turn). Earlier entry means more false signals, so it uses
            a tighter 1.5×ATR stop. Names are tagged by playbook and can qualify for both; filter the
            table by <b>Continuation</b> / <b>Reversal</b> / <b>All</b>.
          </Def>
          <Def term="Risk & regime">
            ATR stop, R-multiple target, a reward:risk filter, volatility-based sizing, and a
            market-regime throttle (SPY vs its 200-day) that damps signals when risk-off.
          </Def>
        </Group>

        <Group title="Scoring metrics">
          <Def term="Score">Final 0–100 rank: the weighted blend of the four factor sub-scores after the regime throttle. Higher = stronger overall setup.</Def>
          <Def term="Sub-scores">Each factor&apos;s standalone 0–1 grade (momentum, trend, catalyst, trigger) before weighting.</Def>
          <Def term="Contributions">How many points each factor added to the final Score — shows <i>why</i> a name scores what it does.</Def>
          <Def term="Momentum percentile">Where the name&apos;s raw momentum ranks against the whole scored universe (0–100).</Def>
          <Def term="Bucket">Strong Buy / Watch / — : the action tier a Score falls into.</Def>
          <Def term="RSI">14-day Relative Strength Index. &gt;70 overbought, &lt;30 oversold; used both as a trigger band and an exit warning.</Def>
          <Def term="5D / 1M">Percentage price change over the last 5 and 21 trading days.</Def>
        </Group>

        <Group title="Risk & exit signals">
          <Def term="Reward:Risk (R:R)">Target distance ÷ stop distance. The engine filters for ~3:1 or better.</Def>
          <Def term="ATR stop">Initial stop = entry − (mult × ATR(14)); ATR (Average True Range) is a volatility measure, so wider-swinging names get wider stops. The multiplier is per-playbook: 2× for continuation, a tighter 1.5× for reversal entries.</Def>
          <Def term="Target">entry + 3R, where R is the initial risk-per-share (entry − stop). One R:R unit of 3:1 gross.</Def>
          <Def term="Suggested shares / dollars">Volatility-based position size so a stop-out risks a fixed fraction of capital.</Def>
          <Def term="Trailing stop (exit)">Standard percentage trail off the position&apos;s high-water mark: level = HWM × (1 − 10%). Ratchets up, never down. 🔴 STOP HIT ≤ level · 🟠 Near (&lt;3% cushion) · 🟡 Watch (&lt;7%) · 🟢 Healthy.</Def>
          <Def term="EMA cross (exit)">Fast/slow EMA gap. Bearish cross (fast below slow) is a red exit flag.</Def>
          <Def term="Target (exit)">Progress toward the R-multiple target; red once hit — take profits.</Def>
          <Def term="RSI (exit)">Overbought warning: 🟡 ≥60 · 🟠 ≥70 · 🔴 ≥80.</Def>
          <Def term="Urgency">Roll-up of the four exit signals: SELL / Consider selling / Watch / Hold.</Def>
          <Def term="Regime & Breadth">Market-wide context: SPY vs its 200-day (risk-on/off) and how much of the universe is advancing / in uptrend.</Def>
        </Group>

        <Group title="Paper-trading statistics">
          <Def term="Equity">Cash + market value of open positions.</Def>
          <Def term="Unrealized / Realized P&L">Open-position gain (marked to the latest price) vs. locked-in gain from closed trades.</Def>
          <Def term="Total P&L / return %">Equity − starting capital, absolute and as a percent of starting capital.</Def>
          <Def term="Win rate">Share of closed trades that were profitable.</Def>
          <Def term="Avg win / avg loss">Mean percentage return of winning vs. losing closed trades.</Def>
          <Def term="R-multiple">Result in units of initial risk: (exit − entry) ÷ (entry − hard stop). +2R means you made twice what you risked. Requires a hard stop set at entry.</Def>
          <Def term="Expectancy (R)">Average R earned per trade = winRate × avgWinR + lossRate × avgLossR. Positive = a profitable edge over many trades.</Def>
          <Def term="Profit factor">Gross profit ÷ gross loss. &gt;1 is profitable; 2.0 means you made $2 for every $1 lost.</Def>
          <Def term="Avg hold">Mean calendar days from entry to exit — is the system actually trading the intended swing horizon?</Def>
          <Def term="Max drawdown">Deepest peak-to-trough dip of the realized-equity curve — worst losing streak, in %.</Def>
          <Def term="Trailing stop (paper)">Same math as the engine exit, but the high-water mark auto-ratchets on every mark. In Alert mode a breach flags red for a manual sell; in Auto-close mode the lot is sold at the stop level automatically.</Def>
          <Def term="Stale">The ticker wasn&apos;t in the latest engine scan, so its price is the last known mark rather than current.</Def>
        </Group>
      </div>
    </details>
  );
}

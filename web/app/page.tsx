import { loadBacktest, loadResults } from "@/lib/data";
import UpdatedAt from "@/components/UpdatedAt";
import type { Quote, RealSeed } from "@/lib/paper";
import StatTiles from "@/components/StatTiles";
import RegimePanel from "@/components/RegimePanel";
import SectorHeatmap from "@/components/SectorHeatmap";
import BacktestPanel from "@/components/BacktestPanel";
import OpportunityTable from "@/components/OpportunityTable";
import PaperProvider from "@/components/PaperProvider";
import PortfolioPanel from "@/components/PortfolioPanel";
import MetricsGlossary from "@/components/MetricsGlossary";
import ThemeToggle from "@/components/ThemeToggle";

// Always read the latest committed data on each request.
export const dynamic = "force-dynamic";

export default async function Page() {
  const r = await loadResults();
  const bt = await loadBacktest();
  const synthetic = r.providers.price === "synthetic";

  // Compact quote map for the client-side positions tracking (mark-to-market off
  // the prices the engine already wrote — no extra data source). ema/atr/rsi let
  // the client recompute the engine's 4-signal exit grade.
  const quotes: Record<string, Quote> = {};
  for (const o of r.opportunities) {
    const sp = o.spark;
    quotes[o.ticker] = {
      ticker: o.ticker,
      price: o.price,
      name: o.name,
      sector: o.sector,
      risk: o.risk,
      emaFast: sp?.ema_fast?.at(-1),
      emaSlow: sp?.ema_slow?.at(-1),
      atr: o.risk?.atr,
      rsi: o.rsi,
    };
  }
  // Every scored name (not just the top_n opportunities) so a holding anywhere in
  // the scan gets the full 4-signal exit grade. Opportunities already set richer
  // fields (name/sector) above, so only fill tickers not seen yet.
  for (const [ticker, m] of Object.entries(r.market ?? {})) {
    if (quotes[ticker]) continue;
    quotes[ticker] = {
      ticker,
      price: m.price,
      emaFast: m.ema_fast,
      emaSlow: m.ema_slow,
      atr: m.atr,
      rsi: m.rsi,
    };
  }
  for (const p of r.positions) {
    if (p.exit && !quotes[p.ticker]) quotes[p.ticker] = { ticker: p.ticker, price: p.exit.price };
  }

  // Held positions from the engine (positions.json) — migrated once into the
  // browser as "Real" lots so the user never edits JSON again.
  const seedReal: RealSeed[] = r.positions.map((p) => ({
    ticker: p.ticker,
    entry_price: p.entry_price,
    shares: p.shares,
    entry_date: p.entry_date,
    high_watermark: (p as { high_watermark?: number }).high_watermark,
  }));

  return (
    <main className="wrap">
      <header className="row spread" style={{ marginBottom: 6 }}>
        <div>
          <h1 style={{ fontSize: 22 }}>Momentum-Swing Dashboard</h1>
          <div className="muted" style={{ fontSize: 13 }}>
            {r.strategy.name} · {r.strategy.horizon}
          </div>
        </div>
        <div className="row" style={{ gap: 10 }}>
          <span className="muted" style={{ fontSize: 12 }}><UpdatedAt iso={r.generated_at} /></span>
          <ThemeToggle />
        </div>
      </header>

      {synthetic && (
        <div className="card" style={{
          borderColor: "color-mix(in srgb, var(--warning) 45%, transparent)",
          background: "color-mix(in srgb, var(--warning) 10%, var(--surface-1))",
          marginBottom: 14, padding: "10px 14px",
        }}>
          ⚠ Showing <b>synthetic demo data</b> — add Polygon &amp; Finnhub API keys to
          <code> .env.local</code> and re-run the engine for live market data.
        </div>
      )}

      <StatTiles r={r} />

      <div className="grid2" style={{ marginTop: 16 }}>
        <RegimePanel regime={r.market_regime} breadth={r.breadth} />
        <SectorHeatmap snapshot={r.snapshot} />
      </div>

      <PaperProvider quotes={quotes} seedReal={seedReal}>
        <section style={{ marginTop: 20 }}>
          <div className="row spread" style={{ marginBottom: 10 }}>
            <h2 style={{ fontSize: 16 }}>Opportunities <span className="muted">({r.opportunities.length})</span></h2>
            <span className="muted" style={{ fontSize: 12 }}>click a row for the full thesis · Log Buy inside</span>
          </div>
          {r.opportunities.length ? (
            <OpportunityTable rows={r.opportunities} />
          ) : (
            <div className="card muted">No names cleared the watch threshold in this scan.</div>
          )}
        </section>

        <section style={{ marginTop: 20 }}>
          <PortfolioPanel />
        </section>
      </PaperProvider>

      <section style={{ marginTop: 20 }}>
        <BacktestPanel bt={bt} />
      </section>

      <section style={{ marginTop: 20 }}>
        <MetricsGlossary weights={r.strategy.factor_weights} />
      </section>

      <footer className="muted" style={{ marginTop: 30, fontSize: 12 }}>
        Data: {r.providers.price} / {r.providers.fundamental}. Decision-support only —
        not investment advice. No orders are placed.
      </footer>
    </main>
  );
}

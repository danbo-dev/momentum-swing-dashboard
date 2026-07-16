"use client";
// Modal forms for the paper-trading account: Buy, Sell, Edit, Settings, Import.
// All state changes go through the usePaper() context (localStorage-backed).
import { useEffect, useState } from "react";
import { money, signedMoney } from "@/lib/format";
import {
  currentPrice,
  stopLevel,
  type Kind,
  type PaperLot,
  type SellReason,
} from "@/lib/paper";
import { usePaper, type BuyPrefill } from "./PaperProvider";

// --- small helpers ---------------------------------------------------------
const num = (s: string): number => {
  const n = parseFloat(s);
  return Number.isFinite(n) ? n : 0;
};

function Modal({
  title,
  sub,
  onClose,
  children,
}: {
  title: string;
  sub?: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="row spread" style={{ marginBottom: 10 }}>
          <div>
            <div className="section-title" style={{ margin: 0 }}>{title}</div>
            {sub && <div className="muted" style={{ fontSize: 12 }}>{sub}</div>}
          </div>
          <button className="btn ghost" onClick={onClose} aria-label="Close">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <label className="field">
      <span className="muted" style={{ fontSize: 12 }}>{label}</span>
      {children}
      {hint && <span className="muted" style={{ fontSize: 11 }}>{hint}</span>}
    </label>
  );
}

// --- Buy -------------------------------------------------------------------
function BuyForm({ prefill }: { prefill?: BuyPrefill }) {
  const { account, quotes, buy, closeDialog } = usePaper();
  const [kind, setKind] = useState<Kind>(account.lastKind ?? "paper");
  const [ticker, setTicker] = useState(prefill?.ticker ?? "");
  const [price, setPrice] = useState(prefill?.price != null ? String(prefill.price) : "");
  const [shares, setShares] = useState("");
  const [stop, setStop] = useState(prefill?.risk?.stop != null ? String(prefill.risk.stop) : "");
  const [target, setTarget] = useState(
    prefill?.risk?.target != null ? String(prefill.risk.target) : "",
  );
  const [trailPct, setTrailPct] = useState(String(account.defaultTrailPct));
  const [note, setNote] = useState("");

  // Pull price/stop/target from the latest scan when the ticker matches.
  function applyQuote(t: string) {
    const q = quotes[t.toUpperCase().trim()];
    if (!q) return;
    if (q.price != null) setPrice(String(q.price));
    if (q.risk) {
      setStop(String(q.risk.stop));
      setTarget(String(q.risk.target));
    }
  }

  const p = num(price);
  const sh = num(shares);
  const cost = p * sh;
  const isPaper = kind === "paper";
  const overspend = isPaper && cost > account.cash + 1e-6;
  const suggested = prefill?.risk?.suggested_shares ?? quotes[ticker.toUpperCase().trim()]?.risk?.suggested_shares;
  const maxShares = p > 0 ? account.cash / p : 0;

  function submit() {
    if (!ticker.trim() || p <= 0 || sh <= 0) return;
    buy({
      ticker,
      kind,
      shares: sh,
      price: p,
      stop: stop ? num(stop) : undefined,
      target: target ? num(target) : undefined,
      trailPct: num(trailPct) || account.defaultTrailPct,
      note: note.trim() || undefined,
    });
    closeDialog();
  }

  return (
    <Modal
      title="Log a Buy"
      sub={isPaper ? `Paper account · cash available ${money(account.cash)}` : "Real holding · no simulated cash"}
      onClose={closeDialog}
    >
      <div className="segmented" style={{ marginBottom: 12 }}>
        <button type="button" className={isPaper ? "on" : ""} onClick={() => setKind("paper")}>
          📝 Paper
        </button>
        <button type="button" className={!isPaper ? "on" : ""} onClick={() => setKind("real")}>
          💵 Real
        </button>
      </div>
      <div className="form-grid">
        <Field label="Ticker">
          <input
            list="paper-quote-tickers"
            value={ticker}
            autoFocus={!prefill}
            onChange={(e) => setTicker(e.target.value)}
            onBlur={(e) => applyQuote(e.target.value)}
            placeholder="AAPL"
          />
        </Field>
        <Field label="Entry price" hint={quotes[ticker.toUpperCase().trim()] ? "from latest scan" : "no live quote — enter manually"}>
          <input value={price} onChange={(e) => setPrice(e.target.value)} inputMode="decimal" placeholder="0.00" />
        </Field>
        <Field
          label="Shares"
          hint={
            [
              suggested != null ? `suggested ${suggested}` : null,
              p > 0 ? `max ${maxShares.toFixed(2)}` : null,
            ]
              .filter(Boolean)
              .join(" · ") || undefined
          }
        >
          <div className="row" style={{ gap: 6 }}>
            <input value={shares} onChange={(e) => setShares(e.target.value)} inputMode="decimal" placeholder="0" style={{ flex: 1 }} />
            {suggested != null && (
              <button type="button" className="btn ghost sm" onClick={() => setShares(String(suggested))}>
                use {suggested}
              </button>
            )}
            {p > 0 && (
              <button type="button" className="btn ghost sm" onClick={() => setShares(String(Math.floor(maxShares)))}>
                max
              </button>
            )}
          </div>
        </Field>
        <Field label="Trailing stop %" hint="10% mirrors the engine">
          <input value={trailPct} onChange={(e) => setTrailPct(e.target.value)} inputMode="decimal" />
        </Field>
        <Field label="Initial hard stop" hint="for R-multiple stats (optional)">
          <input value={stop} onChange={(e) => setStop(e.target.value)} inputMode="decimal" placeholder="optional" />
        </Field>
        <Field label="Target" hint="optional">
          <input value={target} onChange={(e) => setTarget(e.target.value)} inputMode="decimal" placeholder="optional" />
        </Field>
        <Field label="Note">
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="thesis / catalyst" />
        </Field>
      </div>

      <div className="row spread" style={{ marginTop: 12, alignItems: "center" }}>
        <div style={{ fontSize: 13 }}>
          Cost <b className="tnum">{money(cost)}</b>{" "}
          {isPaper && <span className="muted">→ cash after {money(account.cash - cost)}</span>}
          {overspend && <span className="neg" style={{ marginLeft: 8 }}>exceeds cash</span>}
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn ghost" onClick={closeDialog}>Cancel</button>
          <button className="btn primary" onClick={submit} disabled={!ticker.trim() || p <= 0 || sh <= 0}>
            {isPaper ? "Paper" : "Real"} Buy {sh > 0 ? sh : ""} {ticker.toUpperCase()}
          </button>
        </div>
      </div>
    </Modal>
  );
}

// --- Sell ------------------------------------------------------------------
const REASONS: { value: SellReason; label: string }[] = [
  { value: "manual", label: "Manual / discretionary" },
  { value: "target", label: "Target reached" },
  { value: "trailing_stop", label: "Trailing stop" },
  { value: "stop", label: "Hard stop" },
  { value: "signal", label: "Exit signal" },
];

function SellForm({ lot }: { lot: PaperLot }) {
  const { quotes, sell, closeDialog } = usePaper();
  const mark = currentPrice(lot, quotes);
  const [shares, setShares] = useState(String(lot.shares));
  const [price, setPrice] = useState(String(mark));
  const [reason, setReason] = useState<SellReason>("manual");

  const sh = Math.min(num(shares), lot.shares);
  const p = num(price);
  const pnl = (p - lot.entryPrice) * sh;
  const pnlPct = lot.entryPrice > 0 ? ((p - lot.entryPrice) / lot.entryPrice) * 100 : 0;

  function submit() {
    if (sh <= 0 || p <= 0) return;
    sell(lot.id, sh, p, reason);
    closeDialog();
  }

  return (
    <Modal
      title={`Sell ${lot.ticker}`}
      sub={`${lot.shares} sh @ ${money(lot.entryPrice)} entry · trailing stop ${money(stopLevel(lot))}`}
      onClose={closeDialog}
    >
      <div className="form-grid">
        <Field label="Shares to sell" hint={`max ${lot.shares}`}>
          <div className="row" style={{ gap: 6 }}>
            <input value={shares} onChange={(e) => setShares(e.target.value)} inputMode="decimal" style={{ flex: 1 }} />
            <button type="button" className="btn ghost sm" onClick={() => setShares(String(lot.shares))}>all</button>
          </div>
        </Field>
        <Field label="Exit price" hint="prefilled from latest mark">
          <div className="row" style={{ gap: 6 }}>
            <input value={price} onChange={(e) => setPrice(e.target.value)} inputMode="decimal" style={{ flex: 1 }} />
            <button type="button" className="btn ghost sm" onClick={() => setPrice(String(stopLevel(lot)))}>@ stop</button>
          </div>
        </Field>
        <Field label="Reason">
          <select value={reason} onChange={(e) => setReason(e.target.value as SellReason)}>
            {REASONS.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
        </Field>
      </div>

      <div className="row spread" style={{ marginTop: 12, alignItems: "center" }}>
        <div style={{ fontSize: 13 }}>
          Realized{" "}
          <b className={`tnum ${pnl >= 0 ? "pos" : "neg"}`}>
            {signedMoney(pnl)} ({pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(1)}%)
          </b>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn ghost" onClick={closeDialog}>Cancel</button>
          <button className="btn primary" onClick={submit} disabled={sh <= 0 || p <= 0}>
            Sell {sh > 0 ? sh : ""}
          </button>
        </div>
      </div>
    </Modal>
  );
}

// --- Edit ------------------------------------------------------------------
function EditForm({ lot }: { lot: PaperLot }) {
  const { editLot, closeDialog } = usePaper();
  const [shares, setShares] = useState(String(lot.shares));
  const [entryPrice, setEntryPrice] = useState(String(lot.entryPrice));
  const [stop, setStop] = useState(lot.stop != null ? String(lot.stop) : "");
  const [target, setTarget] = useState(lot.target != null ? String(lot.target) : "");
  const [trailPct, setTrailPct] = useState(String(lot.trailPct));
  const [hwm, setHwm] = useState(String(lot.highWatermark));
  const [note, setNote] = useState(lot.note ?? "");

  function submit() {
    editLot(lot.id, {
      shares: num(shares),
      entryPrice: num(entryPrice),
      stop: stop ? num(stop) : undefined,
      target: target ? num(target) : undefined,
      trailPct: num(trailPct),
      highWatermark: num(hwm),
      note: note.trim() || undefined,
    });
    closeDialog();
  }

  return (
    <Modal title={`Edit ${lot.ticker}`} sub="Corrects the lot; cash is rebalanced to the new cost basis." onClose={closeDialog}>
      <div className="form-grid">
        <Field label="Shares"><input value={shares} onChange={(e) => setShares(e.target.value)} inputMode="decimal" /></Field>
        <Field label="Entry price"><input value={entryPrice} onChange={(e) => setEntryPrice(e.target.value)} inputMode="decimal" /></Field>
        <Field label="Trailing stop %"><input value={trailPct} onChange={(e) => setTrailPct(e.target.value)} inputMode="decimal" /></Field>
        <Field label="High-water mark" hint="drives the trailing stop level"><input value={hwm} onChange={(e) => setHwm(e.target.value)} inputMode="decimal" /></Field>
        <Field label="Initial hard stop"><input value={stop} onChange={(e) => setStop(e.target.value)} inputMode="decimal" placeholder="optional" /></Field>
        <Field label="Target"><input value={target} onChange={(e) => setTarget(e.target.value)} inputMode="decimal" placeholder="optional" /></Field>
        <Field label="Note"><input value={note} onChange={(e) => setNote(e.target.value)} /></Field>
      </div>
      <div className="row" style={{ marginTop: 12, gap: 8, justifyContent: "flex-end" }}>
        <button className="btn ghost" onClick={closeDialog}>Cancel</button>
        <button className="btn primary" onClick={submit}>Save</button>
      </div>
    </Modal>
  );
}

// --- Settings --------------------------------------------------------------
function SettingsForm() {
  const { account, setStartingCapital, setDefaultTrailPct, setStopMode, reset, closeDialog } = usePaper();
  const [cap, setCap] = useState(String(account.startingCapital));
  const [trail, setTrail] = useState(String(account.defaultTrailPct));
  const [confirmReset, setConfirmReset] = useState(false);

  function save() {
    setStartingCapital(num(cap));
    setDefaultTrailPct(num(trail));
    closeDialog();
  }

  return (
    <Modal title="Account settings" onClose={closeDialog}>
      <div className="form-grid">
        <Field label="Starting capital" hint="adjusts cash by the difference">
          <input value={cap} onChange={(e) => setCap(e.target.value)} inputMode="decimal" />
        </Field>
        <Field label="Default trailing stop %"><input value={trail} onChange={(e) => setTrail(e.target.value)} inputMode="decimal" /></Field>
      </div>

      <div style={{ marginTop: 12 }}>
        <span className="muted" style={{ fontSize: 12 }}>Trailing-stop trigger</span>
        <div className="row" style={{ gap: 14, marginTop: 6 }}>
          <label className="row" style={{ gap: 6, cursor: "pointer" }}>
            <input type="radio" checked={account.stopMode === "alert"} onChange={() => setStopMode("alert")} />
            <span>Alert only <span className="muted">(flag red, sell manually)</span></span>
          </label>
          <label className="row" style={{ gap: 6, cursor: "pointer" }}>
            <input type="radio" checked={account.stopMode === "auto"} onChange={() => setStopMode("auto")} />
            <span>Auto-close <span className="muted">(sell at stop on breach)</span></span>
          </label>
        </div>
        <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
          Marks are end-of-day (engine cadence), so stops fire on observed closes — overnight
          gaps can exceed the level, so a fill at the exact stop is an approximation.
        </div>
      </div>

      <div className="row spread" style={{ marginTop: 16, alignItems: "center" }}>
        {confirmReset ? (
          <span className="row" style={{ gap: 8 }}>
            <span className="neg" style={{ fontSize: 13 }}>Clear all lots & trades?</span>
            <button className="btn danger sm" onClick={() => { reset(); closeDialog(); }}>Yes, reset</button>
            <button className="btn ghost sm" onClick={() => setConfirmReset(false)}>No</button>
          </span>
        ) : (
          <button className="btn ghost sm" onClick={() => setConfirmReset(true)}>Reset account…</button>
        )}
        <div className="row" style={{ gap: 8 }}>
          <button className="btn ghost" onClick={closeDialog}>Cancel</button>
          <button className="btn primary" onClick={save}>Save</button>
        </div>
      </div>
    </Modal>
  );
}

// --- Import ----------------------------------------------------------------
function ImportForm() {
  const { importText, closeDialog } = usePaper();
  const [text, setText] = useState("");
  const [err, setErr] = useState<string | null>(null);

  function submit() {
    try {
      importText(text);
      closeDialog();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Invalid JSON");
    }
  }

  return (
    <Modal title="Import account" sub="Paste a previously exported paper-trading JSON (replaces current state)." onClose={closeDialog}>
      <textarea
        value={text}
        onChange={(e) => { setText(e.target.value); setErr(null); }}
        placeholder='{ "version": 1, "lots": [...], "trades": [...] }'
        rows={10}
        style={{ width: "100%", fontFamily: "var(--mono, monospace)", fontSize: 12 }}
      />
      {err && <div className="neg" style={{ fontSize: 12, marginTop: 6 }}>{err}</div>}
      <div className="row" style={{ marginTop: 12, gap: 8, justifyContent: "flex-end" }}>
        <button className="btn ghost" onClick={closeDialog}>Cancel</button>
        <button className="btn primary" onClick={submit} disabled={!text.trim()}>Import</button>
      </div>
    </Modal>
  );
}

// --- Dispatcher ------------------------------------------------------------
export default function PaperDialogs() {
  const { dialog, account } = usePaper();
  if (!dialog) return null;
  if (dialog.kind === "buy") return <BuyForm prefill={dialog.prefill} />;
  if (dialog.kind === "settings") return <SettingsForm />;
  if (dialog.kind === "import") return <ImportForm />;
  const lot = "lotId" in dialog ? account.lots.find((l) => l.id === dialog.lotId) : undefined;
  if (dialog.kind === "sell" && lot) return <SellForm lot={lot} />;
  if (dialog.kind === "edit" && lot) return <EditForm lot={lot} />;
  return null;
}

"use client";
// Client context that owns the paper-trading account and the open dialog. Wraps
// the interactive sections (Opportunities + Paper Trading) so a "Paper Buy" click
// in the Opportunity table can open the Buy dialog rendered here.
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import {
  usePaperAccount,
  type PaperApi,
  type Quote,
  type RealSeed,
  type RiskBlock,
} from "@/lib/paper";
import PaperDialogs from "./PaperTradeDialogs";

export interface BuyPrefill {
  ticker: string;
  price?: number;
  risk?: RiskBlock;
  name?: string;
}

export type Dialog =
  | { kind: "buy"; prefill?: BuyPrefill }
  | { kind: "sell"; lotId: string }
  | { kind: "edit"; lotId: string }
  | { kind: "settings" }
  | { kind: "import" }
  | null;

interface PaperCtx extends PaperApi {
  quotes: Record<string, Quote>;
  dialog: Dialog;
  openBuy: (prefill?: BuyPrefill) => void;
  openSell: (lotId: string) => void;
  openEdit: (lotId: string) => void;
  openSettings: () => void;
  openImport: () => void;
  closeDialog: () => void;
}

const Ctx = createContext<PaperCtx | null>(null);

export function usePaper(): PaperCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("usePaper must be used inside <PaperProvider>");
  return c;
}

export default function PaperProvider({
  quotes,
  seedReal = [],
  children,
}: {
  quotes: Record<string, Quote>;
  seedReal?: RealSeed[];
  children: React.ReactNode;
}) {
  const api = usePaperAccount();
  const [dialog, setDialog] = useState<Dialog>(null);

  // Once the account has loaded from localStorage: import the engine's held
  // positions as Real lots (once), then mark to market — ratchet HWMs and, in
  // auto mode, fire any breached trailing stops.
  const { mark, migrateRealSeed, mounted } = api;
  useEffect(() => {
    if (!mounted) return;
    migrateRealSeed(seedReal);
    mark(quotes);
  }, [mounted, quotes, seedReal, mark, migrateRealSeed]);

  const value = useMemo<PaperCtx>(
    () => ({
      ...api,
      quotes,
      dialog,
      openBuy: (prefill) => setDialog({ kind: "buy", prefill }),
      openSell: (lotId) => setDialog({ kind: "sell", lotId }),
      openEdit: (lotId) => setDialog({ kind: "edit", lotId }),
      openSettings: () => setDialog({ kind: "settings" }),
      openImport: () => setDialog({ kind: "import" }),
      closeDialog: () => setDialog(null),
    }),
    [api, quotes, dialog],
  );

  return (
    <Ctx.Provider value={value}>
      {children}
      <datalist id="paper-quote-tickers">
        {Object.values(quotes).map((q) => (
          <option key={q.ticker} value={q.ticker}>
            {q.name ? `${q.name} · ${q.price}` : String(q.price)}
          </option>
        ))}
      </datalist>
      <PaperDialogs />
    </Ctx.Provider>
  );
}

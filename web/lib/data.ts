import { promises as fs } from "fs";
import path from "path";
import type { Backtest, Results } from "./types";

// Read the engine's committed JSON from public/data at request time, so each
// deploy (triggered by the engine's data commit) serves fresh data.
const DATA_DIR = path.join(process.cwd(), "public", "data");

export async function loadResults(): Promise<Results> {
  const raw = await fs.readFile(path.join(DATA_DIR, "results.json"), "utf-8");
  return JSON.parse(raw) as Results;
}

export async function loadBacktest(): Promise<Backtest | null> {
  try {
    const raw = await fs.readFile(path.join(DATA_DIR, "backtest.json"), "utf-8");
    return JSON.parse(raw) as Backtest;
  } catch {
    return null;
  }
}

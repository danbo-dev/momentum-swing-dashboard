"use client";
// Collapsible page section. Open/closed state persists per-section in localStorage,
// so the layout you leave is the layout you come back to — the point is to stop
// scrolling past 40 opportunities to reach your positions.
import { useEffect, useState } from "react";

const KEY = "msd_sections_v1";

function readState(): Record<string, boolean> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.localStorage.getItem(KEY) || "{}");
  } catch {
    return {};
  }
}

export default function Collapsible({
  id,
  title,
  count,
  defaultOpen = true,
  right,
  children,
}: {
  id: string;
  title: string;
  count?: number | string;
  defaultOpen?: boolean;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  // Start from `defaultOpen` on both server and first client paint, then adopt the
  // stored value after mount — reading localStorage during render would mismatch SSR.
  const [open, setOpen] = useState(defaultOpen);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = readState()[id];
    if (typeof stored === "boolean") setOpen(stored);
    setMounted(true);
  }, [id]);

  useEffect(() => {
    if (!mounted) return;
    try {
      window.localStorage.setItem(KEY, JSON.stringify({ ...readState(), [id]: open }));
    } catch { /* private mode / quota — collapsing still works, just isn't remembered */ }
  }, [id, open, mounted]);

  return (
    <section className="card" style={{ marginTop: 16 }}>
      <div className="row spread" style={{ alignItems: "center" }}>
        <button
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-controls={`sec-${id}`}
          className="btn ghost"
          style={{
            display: "flex", alignItems: "center", gap: 8,
            border: "none", padding: "2px 0", background: "none",
            font: "inherit", fontWeight: 650, fontSize: 16, cursor: "pointer",
          }}
        >
          <span style={{ fontSize: 12, opacity: 0.7, width: 12 }}>{open ? "▾" : "▸"}</span>
          {title}
          {count !== undefined && <span className="muted" style={{ fontWeight: 400 }}>({count})</span>}
        </button>
        {right}
      </div>
      <div id={`sec-${id}`} hidden={!open} style={{ marginTop: open ? 12 : 0 }}>
        {open && children}
      </div>
    </section>
  );
}

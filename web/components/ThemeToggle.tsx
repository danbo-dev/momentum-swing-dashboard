"use client";
import { useEffect, useState } from "react";

type Mode = "light" | "dark" | "system";

export default function ThemeToggle() {
  const [mode, setMode] = useState<Mode>("system");

  useEffect(() => {
    const saved = (localStorage.getItem("theme") as Mode) || "system";
    setMode(saved);
  }, []);

  function apply(next: Mode) {
    setMode(next);
    localStorage.setItem("theme", next);
    const root = document.documentElement;
    if (next === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", next);
  }

  const order: Mode[] = ["system", "light", "dark"];
  const label = { system: "🖥 System", light: "☀ Light", dark: "🌙 Dark" }[mode];

  return (
    <button
      className="btn"
      onClick={() => apply(order[(order.indexOf(mode) + 1) % order.length])}
      title="Toggle theme"
    >
      {label}
    </button>
  );
}

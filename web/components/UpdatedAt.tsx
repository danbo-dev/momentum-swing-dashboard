"use client";

import { useEffect, useState } from "react";
import { fmtDate } from "@/lib/format";

// Renders the "Updated …" timestamp in the VIEWER's local time zone. page.tsx is
// a server component, so formatting there uses the server zone (UTC on Vercel).
// We defer formatting to a client effect so it reflects the visitor's own clock;
// before mount we show the raw ISO's date/time is unknown, so render a neutral
// placeholder to avoid a hydration mismatch.
export default function UpdatedAt({ iso }: { iso: string }) {
  const [text, setText] = useState<string | null>(null);
  useEffect(() => {
    setText(fmtDate(iso));
  }, [iso]);
  return <span suppressHydrationWarning>Updated {text ?? "…"}</span>;
}

export const pct = (n: number, digits = 1) =>
  `${n > 0 ? "+" : ""}${n.toFixed(digits)}%`;

export const money = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });

export const signedMoney = (n: number) => `${n > 0 ? "+" : n < 0 ? "−" : ""}${money(Math.abs(n))}`;

export const rMult = (n: number | null | undefined) =>
  n == null ? "—" : `${n >= 0 ? "+" : "−"}${Math.abs(n).toFixed(2)}R`;

// Formats an ISO timestamp in the viewer's local time zone. Because the browser
// (not the server) supplies the zone, call this on the client — see
// <UpdatedAt> — otherwise it renders in the server's zone (UTC on Vercel).
export const fmtDate = (iso: string) => {
  try {
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    });
  } catch {
    return iso;
  }
};

export const bucketLabel: Record<string, string> = {
  strong_buy: "Strong Buy",
  watch: "Watch",
  none: "—",
};

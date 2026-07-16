import type { Spark } from "@/lib/types";

interface Props {
  spark: Spark;
  width?: number;
  height?: number;
  showEma?: boolean;
}

function path(values: number[], w: number, h: number, min: number, max: number, pad = 2) {
  const span = max - min || 1;
  const n = values.length;
  return values
    .map((v, i) => {
      const x = pad + (i / (n - 1 || 1)) * (w - pad * 2);
      const y = pad + (1 - (v - min) / span) * (h - pad * 2);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

// Single-series price sparkline (line colored by net direction) with faint EMAs.
export default function Sparkline({ spark, width = 132, height = 34, showEma = true }: Props) {
  const { close, ema_fast, ema_slow } = spark;
  if (!close?.length) return null;
  const all = showEma ? [...close, ...ema_fast, ...ema_slow] : close;
  const min = Math.min(...all);
  const max = Math.max(...all);
  const up = close[close.length - 1] >= close[0];
  const stroke = up ? "var(--pos)" : "var(--neg)";
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden>
      {showEma && (
        <>
          <path d={path(ema_slow, width, height, min, max)} fill="none"
            stroke="var(--baseline)" strokeWidth="1" opacity="0.7" />
          <path d={path(ema_fast, width, height, min, max)} fill="none"
            stroke="var(--f-momentum)" strokeWidth="1" opacity="0.55" />
        </>
      )}
      <path d={path(close, width, height, min, max)} fill="none"
        stroke={stroke} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

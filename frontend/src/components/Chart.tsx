import { useEffect, useId, useRef, useState } from "react";
import type { StimulusChart, StimulusTable } from "../api/types";
import { columnFormatter } from "../lib/format";

const M = { l: 70, r: 18, t: 16, b: 62 };

/**
 * The viewBox follows the rendered width (340-600 units) so axis text stays
 * close to its nominal size on a phone instead of shrinking with the drawing.
 */
function useChartWidth() {
  const ref = useRef<HTMLElement>(null);
  const [width, setWidth] = useState(600);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 600;
      setWidth(Math.max(340, Math.min(600, Math.round(w))));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return { ref, width };
}

const INK = "#1b2a30";
const GRID = "#c5cfd1";
const DASHES = ["", "7 4", "2 4"];

function niceStep(range: number, target: number): number {
  if (range <= 0 || !Number.isFinite(range)) return 1;
  const raw = range / target;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const nice = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10;
  return nice * mag;
}

function ticksFor(lo: number, hi: number, step: number): number[] {
  const out: number[] = [];
  const start = Math.ceil(lo / step - 1e-9) * step;
  for (let v = start; v <= hi + step * 1e-6; v += step) out.push(Number(v.toPrecision(12)));
  return out;
}

function fmtTick(v: number, step: number): string {
  const decimals = step >= 1 ? 0 : Math.min(4, Math.ceil(-Math.log10(step)));
  return v.toFixed(decimals);
}

function toNum(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v))) return Number(v);
  return null;
}

function Marker({ shape, x, y }: { shape: number; x: number; y: number }) {
  if (shape % 3 === 1) return <rect x={x - 4.5} y={y - 4.5} width={9} height={9} fill="#fff" stroke={INK} strokeWidth={2} />;
  if (shape % 3 === 2)
    return <path d={`M${x},${y - 6} L${x + 5.5},${y + 4} L${x - 5.5},${y + 4} Z`} fill={INK} stroke={INK} strokeWidth={1} />;
  return <circle cx={x} cy={y} r={4.5} fill={INK} />;
}

/**
 * Hand-drawn SVG chart. Series are distinguished by dash pattern, marker shape
 * and bar hatching (never by colour alone) so it reads in black-and-white print.
 */
export function Chart({ chart, table }: { chart: StimulusChart; table: StimulusTable }) {
  const uid = useId().replaceAll(":", "");
  const { ref, width: W } = useChartWidth();
  const H = Math.round(W * 0.57);
  const PW = W - M.l - M.r;
  const PH = H - M.t - M.b;
  const titleId = `${uid}-t`;
  const descId = `${uid}-d`;
  const rows = table.rows;
  const series = chart.series.length ? chart.series : [];

  const values = rows.flatMap((r) => series.map((s) => toNum(r[s.key]))).filter((v): v is number => v !== null);
  const dataMin = values.length ? Math.min(...values) : 0;
  const dataMax = values.length ? Math.max(...values) : 1;
  let yLo = chart.y.min ?? (dataMin >= 0 ? 0 : dataMin);
  let yHiRaw = chart.y.max ?? dataMax;
  if (yHiRaw <= yLo) yHiRaw = yLo + 1;
  const yStep = niceStep(yHiRaw - yLo, 5);
  if (chart.y.min == null) yLo = Math.floor(yLo / yStep) * yStep;
  const yHi = chart.y.max ?? Math.ceil((yHiRaw * 1.0001) / yStep) * yStep;
  const yTicks = ticksFor(yLo, yHi, yStep);
  const sy = (v: number) => M.t + PH - ((v - yLo) / (yHi - yLo || 1)) * PH;

  const xFmt = columnFormatter(rows.map((r) => r[chart.x.key]));
  const xNums = rows.map((r) => toNum(r[chart.x.key]));
  const numericX = chart.type === "line" && xNums.every((v) => v !== null) && rows.length > 1;

  let sx: (i: number) => number;
  let xTicks: { pos: number; label: string }[];
  let band = 0;
  if (numericX) {
    const xs = xNums as number[];
    const xMinD = Math.min(...xs);
    const xMaxD = Math.max(...xs);
    const xStep = niceStep(xMaxD - xMinD, W < 450 ? 4 : 6);
    const xLo = Math.floor(xMinD / xStep) * xStep;
    const xHi = Math.ceil(xMaxD / xStep) * xStep || xLo + 1;
    const scale = (v: number) => M.l + ((v - xLo) / (xHi - xLo || 1)) * PW;
    sx = (i) => scale(xs[i]);
    xTicks = ticksFor(xLo, xHi, xStep).map((v) => ({ pos: scale(v), label: fmtTick(v, xStep) }));
  } else {
    band = PW / Math.max(rows.length, 1);
    sx = (i) => M.l + band * (i + 0.5);
    xTicks = rows.map((r, i) => ({ pos: sx(i), label: xFmt(r[chart.x.key]) }));
  }

  const kind = chart.type === "bar" ? "Bar graph" : "Line graph";
  const seriesNames = series.map((s) => s.label).join(", ");
  const desc = `${kind} of ${seriesNames || chart.y.label} against ${chart.x.label}. The exact values are in the table "${table.caption}".`;

  const barGroupW = band * 0.72;
  const barW = series.length ? barGroupW / series.length : barGroupW;

  return (
    <figure ref={ref} className="keep my-4 max-w-2xl">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-labelledby={`${titleId} ${descId}`}
        className="block h-auto w-full"
        style={{ fontFamily: "var(--font-serif)", fontVariantNumeric: "lining-nums tabular-nums" }}
      >
        <title id={titleId}>{chart.title}</title>
        <desc id={descId}>{desc}</desc>
        <defs>
          <pattern id={`${uid}-hatch`} patternUnits="userSpaceOnUse" width="7" height="7" patternTransform="rotate(45)">
            <rect width="7" height="7" fill="#fff" />
            <line x1="0" y1="0" x2="0" y2="7" stroke={INK} strokeWidth="2.2" />
          </pattern>
          <pattern id={`${uid}-dots`} patternUnits="userSpaceOnUse" width="6" height="6">
            <rect width="6" height="6" fill="#fff" />
            <circle cx="3" cy="3" r="1.3" fill={INK} />
          </pattern>
        </defs>

        {/* grid + y axis */}
        {yTicks.map((v) => (
          <g key={`y${v}`}>
            <line x1={M.l} x2={M.l + PW} y1={sy(v)} y2={sy(v)} stroke={GRID} strokeWidth={1} />
            <text x={M.l - 8} y={sy(v)} dy="0.35em" textAnchor="end" fontSize="14" fill={INK}>
              {fmtTick(v, yStep)}
            </text>
          </g>
        ))}
        {numericX
          ? xTicks.map((t) => (
              <line key={`gx${t.pos}`} x1={t.pos} x2={t.pos} y1={M.t} y2={M.t + PH} stroke={GRID} strokeWidth={1} />
            ))
          : null}

        {/* data */}
        {chart.type === "bar"
          ? rows.map((r, i) =>
              series.map((s, si) => {
                const v = toNum(r[s.key]);
                if (v === null) return null;
                const x = sx(i) - barGroupW / 2 + si * barW;
                const y0 = sy(Math.max(yLo, 0));
                const y1 = sy(v);
                const fill = si % 3 === 0 ? "#4b5b61" : si % 3 === 1 ? `url(#${uid}-hatch)` : `url(#${uid}-dots)`;
                return (
                  <rect
                    key={`${i}-${s.key}`}
                    x={x + 1}
                    y={Math.min(y0, y1)}
                    width={Math.max(barW - 2, 1)}
                    height={Math.abs(y0 - y1)}
                    fill={fill}
                    stroke={INK}
                    strokeWidth={1.2}
                  />
                );
              }),
            )
          : series.map((s, si) => {
              const pts = rows
                .map((r, i) => {
                  const v = toNum(r[s.key]);
                  return v === null ? null : { x: sx(i), y: sy(v) };
                })
                .filter((p): p is { x: number; y: number } => p !== null);
              return (
                <g key={s.key}>
                  <polyline
                    points={pts.map((p) => `${p.x},${p.y}`).join(" ")}
                    fill="none"
                    stroke={INK}
                    strokeWidth={2.2}
                    strokeDasharray={DASHES[si % DASHES.length] || undefined}
                    strokeLinejoin="round"
                  />
                  {pts.map((p, pi) => (
                    <Marker key={pi} shape={si} x={p.x} y={p.y} />
                  ))}
                </g>
              );
            })}

        {/* axes */}
        <line x1={M.l} x2={M.l} y1={M.t} y2={M.t + PH} stroke={INK} strokeWidth={1.5} />
        <line x1={M.l} x2={M.l + PW} y1={M.t + PH} y2={M.t + PH} stroke={INK} strokeWidth={1.5} />
        {xTicks.map((t) => (
          <g key={`xt${t.pos}`}>
            <line x1={t.pos} x2={t.pos} y1={M.t + PH} y2={M.t + PH + 5} stroke={INK} strokeWidth={1.5} />
            <text x={t.pos} y={M.t + PH + 21} textAnchor="middle" fontSize="14" fill={INK}>
              {t.label}
            </text>
          </g>
        ))}
        <text x={M.l + PW / 2} y={H - 10} textAnchor="middle" fontSize="15" fontWeight="700" fill={INK}>
          {chart.x.label}
        </text>
        <text
          transform={`translate(18 ${M.t + PH / 2}) rotate(-90)`}
          textAnchor="middle"
          fontSize="15"
          fontWeight="700"
          fill={INK}
        >
          {chart.y.label}
        </text>
      </svg>
      {series.length > 1 ? (
        <ul className="mt-1 flex flex-wrap gap-x-5 gap-y-1 font-sans text-sm" aria-label="Legend">
          {series.map((s, si) => (
            <li key={s.key} className="flex items-center gap-2">
              <svg width="34" height="14" aria-hidden="true">
                {chart.type === "bar" ? (
                  <rect
                    x="8"
                    y="1"
                    width="18"
                    height="12"
                    stroke={INK}
                    fill={si % 3 === 0 ? "#4b5b61" : si % 3 === 1 ? `url(#${uid}-hatch)` : `url(#${uid}-dots)`}
                  />
                ) : (
                  <>
                    <line x1="0" x2="34" y1="7" y2="7" stroke={INK} strokeWidth="2" strokeDasharray={DASHES[si % 3] || undefined} />
                    <Marker shape={si} x={17} y={7} />
                  </>
                )}
              </svg>
              {s.label}
            </li>
          ))}
        </ul>
      ) : null}
      <figcaption className="mt-1 font-sans text-sm text-muted">
        <span className="font-bold text-ink">{chart.title}.</span> The values plotted here are listed in the table “
        {table.caption}”.
      </figcaption>
    </figure>
  );
}

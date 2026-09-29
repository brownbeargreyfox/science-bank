import type {
  CoverageRow,
  PrintStandard,
  Provenance,
  StimulusBody,
  StimulusChart,
  StimulusSection,
  StimulusTable,
} from "../api/types";

/** "organizing_data" -> "Organizing data" */
export function humanize(key: string): string {
  const s = key.replaceAll("_", " ").replaceAll("-", " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const dateFmt = new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  // A bare YYYY-MM-DD is a calendar date, not a UTC instant.
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  const d = m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : dateFmt.format(d);
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : dateTimeFmt.format(d);
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}
function str(v: unknown): string {
  return typeof v === "string" ? v : v == null ? "" : String(v);
}
function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** Validates the untyped stimulus body into a shape the renderer can trust. */
export function parseStimulus(raw: unknown): StimulusBody | null {
  if (!isRecord(raw)) return null;
  const tables: StimulusTable[] = Array.isArray(raw.tables)
    ? raw.tables.filter(isRecord).map((t) => ({
        caption: str(t.caption),
        columns: Array.isArray(t.columns)
          ? t.columns.filter(isRecord).map((c) => ({ key: str(c.key), label: str(c.label) || str(c.key) }))
          : [],
        rows: Array.isArray(t.rows) ? t.rows.filter(isRecord) : [],
      }))
    : [];
  const charts: StimulusChart[] = Array.isArray(raw.charts)
    ? raw.charts.filter(isRecord).flatMap((c) => {
        const x = isRecord(c.x) ? c.x : {};
        const y = isRecord(c.y) ? c.y : {};
        const tableIndex = num(c.table_index);
        if (tableIndex === null) return [];
        return [
          {
            type: c.type === "bar" ? "bar" : "line",
            title: str(c.title),
            x: { key: str(x.key), label: str(x.label) },
            y: { label: str(y.label), min: num(y.min), max: num(y.max) },
            series: Array.isArray(c.series)
              ? c.series.filter(isRecord).map((s) => ({ key: str(s.key), label: str(s.label) || str(s.key) }))
              : [],
            table_index: tableIndex,
          } satisfies StimulusChart,
        ];
      })
    : [];
  const sections: StimulusSection[] = Array.isArray(raw.sections)
    ? raw.sections.filter(isRecord).map((s) => ({
        heading: str(s.heading),
        text: str(s.text),
        table_index: num(s.table_index),
      }))
    : [];
  return { kind: str(raw.kind), title: str(raw.title), intro: str(raw.intro), sections, tables, charts };
}

export function parseProvenance(raw: unknown): Provenance {
  return isRecord(raw) ? (raw as Provenance) : {};
}

export function parseCoverage(raw: unknown): CoverageRow[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter(isRecord).map((r) => ({
    standard_id: num(r.standard_id) ?? undefined,
    code: str(r.code),
    course: str(r.course) || undefined,
    count: num(r.count) ?? undefined,
    performance_expectation: str(r.performance_expectation) || undefined,
  }));
}

export function parsePrintStandards(raw: unknown): PrintStandard[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter(isRecord).map((r) => ({
    code: str(r.code),
    course: str(r.course) || undefined,
    use_year: str(r.use_year) || undefined,
    performance_expectation: str(r.performance_expectation) || undefined,
  }));
}

function decimalsOf(n: number): number {
  if (Number.isInteger(n)) return 0;
  const s = String(n);
  const i = s.indexOf(".");
  return i < 0 ? 0 : Math.min(s.length - i - 1, 4);
}

/**
 * Returns a formatter that prints every number in a column with the same
 * number of decimals (so pH 5 shows as "5.0" beside 4.5 and 5.5).
 */
export function columnFormatter(values: unknown[]): (v: unknown) => string {
  const nums = values.filter((v): v is number => typeof v === "number" && Number.isFinite(v));
  const decimals = nums.reduce((m, n) => Math.max(m, decimalsOf(n)), 0);
  return (v) => {
    if (typeof v === "number" && Number.isFinite(v)) return v.toFixed(decimals);
    return str(v);
  };
}

export function pluralize(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** Only allow same-origin, single-slash paths as a post-login destination. */
export function safeNext(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return "/";
  if (next.startsWith("/login")) return "/";
  return next;
}

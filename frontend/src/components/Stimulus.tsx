import type { StimulusBody, StimulusTable } from "../api/types";
import { columnFormatter, parseStimulus } from "../lib/format";
import { Chart } from "./Chart";

export function DataTable({ table }: { table: StimulusTable }) {
  const fmts = table.columns.map((c) => columnFormatter(table.rows.map((r) => r[c.key])));
  return (
    <div className="keep my-3 max-w-full overflow-x-auto">
      <table className="data-table">
        <caption>{table.caption}</caption>
        <thead>
          <tr>
            {table.columns.map((c) => (
              <th key={c.key} scope="col">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((r, ri) => (
            <tr key={ri}>
              {table.columns.map((c, ci) =>
                ci === 0 ? (
                  <th key={c.key} scope="row" className="font-normal">
                    {fmts[ci](r[c.key])}
                  </th>
                ) : (
                  <td key={c.key}>{fmts[ci](r[c.key])}</td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TableBlock({ body, index }: { body: StimulusBody; index: number }) {
  const table = body.tables[index];
  if (!table) return null;
  return (
    <>
      <DataTable table={table} />
      {body.charts
        .filter((c) => c.table_index === index)
        .map((c, i) => (
          <Chart key={i} chart={c} table={table} />
        ))}
    </>
  );
}

/**
 * Renders a stimulus in the order the question families define:
 * title, intro, then each section (with its table and charts directly after
 * the text), then any tables no section referenced.
 */
export function Stimulus({
  body: raw,
  level = 3,
  className = "",
}: {
  body: unknown;
  level?: 2 | 3;
  className?: string;
}) {
  const body = parseStimulus(raw);
  if (!body) return <p className="text-muted">This stimulus could not be displayed.</p>;
  const Title = level === 2 ? "h2" : "h3";
  const Sub = level === 2 ? "h3" : "h4";
  const referenced = new Set(
    body.sections.map((s) => s.table_index).filter((i): i is number => typeof i === "number"),
  );
  const unreferenced = body.tables.map((_, i) => i).filter((i) => !referenced.has(i));

  return (
    <div className={`booklet ${className}`}>
      <Title className="keep-with-next mb-2 text-xl font-semibold">{body.title}</Title>
      {body.intro ? <p className="mb-3 max-w-[70ch] whitespace-pre-line">{body.intro}</p> : null}
      {body.sections.map((s, i) => (
        <div key={i} className="mb-3">
          {s.heading ? <Sub className="keep-with-next mb-1 text-[1.0625rem] font-semibold">{s.heading}</Sub> : null}
          {s.text ? <p className="max-w-[70ch] whitespace-pre-line">{s.text}</p> : null}
          {typeof s.table_index === "number" ? <TableBlock body={body} index={s.table_index} /> : null}
        </div>
      ))}
      {unreferenced.map((i) => (
        <TableBlock key={`t${i}`} body={body} index={i} />
      ))}
    </div>
  );
}

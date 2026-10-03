import { Link } from "react-router";
import { accuracyText, limitedResponses } from "../../lib/results";
import { ErrorNotice, Loading, Pill } from "../ui";
import { useCoverage, useSummary } from "./data";
import { Widget } from "./Widget";

export function StandardsCoverageWidget({ courseId }: { courseId: number | null }) {
  const { pending, error, total, used, ready, rest } = useCoverage(courseId);
  const width = (n: number) => (total ? `${(n / total) * 100}%` : "0%");
  return (
    <Widget
      id="dashboard-coverage"
      title="Standards coverage"
      className="lg:col-span-2"
      actions={
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
          Used means a teacher recorded results for it
          <Link to={`/coverage${courseId ? `?course=${courseId}` : ""}`}>Open the coverage grid</Link>
        </span>
      }
    >
      <ErrorNotice error={error} />
      {pending ? (
        <Loading />
      ) : (
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <div
            className="flex h-3 min-w-[12rem] flex-1 overflow-hidden bg-line-soft"
            role="img"
            aria-label={`Of ${total} standards: ${used} used in a recorded assessment, ${ready} with a generator but not used yet, ${rest} with no generator and not used yet`}
          >
            <span className="bg-accent" style={{ width: width(used) }} />
            <span className="bg-bound" style={{ width: width(ready) }} />
          </div>
          <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            <li className="flex items-center gap-1.5">
              <span className="h-3 w-3 shrink-0 bg-accent" aria-hidden="true" />
              <span>Used {used}</span>
            </li>
            <li className="flex items-center gap-1.5">
              <span className="h-3 w-3 shrink-0 bg-bound" aria-hidden="true" />
              <span>Ready, not used {ready}</span>
            </li>
            <li className="flex items-center gap-1.5">
              <span className="h-3 w-3 shrink-0 border border-line bg-line-soft" aria-hidden="true" />
              <span>No generator yet {rest}</span>
            </li>
          </ul>
        </div>
      )}
    </Widget>
  );
}

export function ResultsReviewWidget({ courseId }: { courseId: number | null }) {
  const summary = useSummary(courseId);
  const rows = (summary.data?.items ?? []).filter((row) => row.accuracy !== null).slice(0, 3);
  return (
    <Widget
      id="dashboard-results"
      title="Review these first"
      actions={
        <Link to="/results" className="text-sm font-bold">
          All results
        </Link>
      }
    >
      <ErrorNotice error={summary.error} />
      {summary.isPending ? (
        <Loading />
      ) : rows.length === 0 ? (
        <p className="text-muted">Record a use from an assessment page, then enter results.</p>
      ) : (
        <ul className="divide-y divide-line-soft">
          {rows.map((row) => (
            <li key={row.question_id} className="flex items-baseline justify-between gap-3 py-2">
              <Link to={`/questions/${row.question_id}`} className="min-w-0 truncate font-bold" title={row.stem}>
                {row.stem}
              </Link>
              <span className="flex shrink-0 items-center gap-2 text-sm">
                <code>{row.standard_code}</code>
                <strong>{accuracyText(row.correct, row.attempted)}</strong>
                {limitedResponses(row.attempted) ? <Pill>Limited response count</Pill> : null}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Widget>
  );
}

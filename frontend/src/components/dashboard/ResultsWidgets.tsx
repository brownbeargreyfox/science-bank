import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api, cleanQuery, unwrap } from "../../api/client";
import { useFamilies, useStandards } from "../../api/queries";
import { accuracyText, limitedResponses } from "../../lib/results";
import { ErrorNotice, Loading, Pill } from "../ui";
import { Widget } from "./Widget";

function useSummary(courseId: number | null) {
  return useQuery({
    queryKey: ["results", "summary", "dashboard", courseId],
    queryFn: () =>
      unwrap(
        api.GET("/api/results/summary", {
          params: { query: cleanQuery({ course_id: courseId ?? undefined, limit: 200 }) },
        }),
      ),
    enabled: courseId !== null,
  });
}

export function StandardsCoverageWidget({ courseId }: { courseId: number | null }) {
  const standards = useStandards({ course_id: courseId }, courseId !== null);
  const families = useFamilies();
  const summary = useSummary(courseId);
  if (standards.isPending || families.isPending || summary.isPending)
    return (
      <Widget id="dashboard-coverage" title="Standards coverage">
        <Loading />
      </Widget>
    );
  if (standards.error || families.error || summary.error)
    return (
      <Widget id="dashboard-coverage" title="Standards coverage">
        <ErrorNotice error={standards.error ?? families.error ?? summary.error} />
      </Widget>
    );
  const all = standards.data ?? [];
  const used = new Set((summary.data?.items ?? []).map((row) => row.standard_id));
  const generated = new Set(
    (families.data ?? []).flatMap((family) => family.bindings.flatMap((binding) => binding.standard_ids)),
  );
  const usedCount = all.filter((standard) => used.has(standard.id)).length;
  const generatedCount = all.filter((standard) => !used.has(standard.id) && generated.has(standard.id)).length;
  const neither = Math.max(0, all.length - usedCount - generatedCount);
  const width = (n: number) => (all.length ? `${(n / all.length) * 100}%` : "0%");
  return (
    <Widget id="dashboard-coverage" title="Standards coverage">
      <div
        className="flex h-3 overflow-hidden rounded bg-line-soft"
        aria-label={`${usedCount} of ${all.length} used in a recorded assessment`}
      >
        <span className="bg-petrol" style={{ width: width(usedCount) }} />
        <span className="bg-bound" style={{ width: width(generatedCount) }} />
        <span className="bg-line-soft" style={{ width: width(neither) }} />
      </div>
      <ul className="mt-3 space-y-1 text-sm">
        <li>
          <span className="font-bold">Used in a recorded assessment:</span> {usedCount} of {all.length}
        </li>
        <li>
          <span className="font-bold">Has a question generator:</span> {generatedCount} of {all.length}
        </li>
        <li>
          <span className="font-bold">Neither:</span> {neither} of {all.length}
        </li>
      </ul>
      <p className="mt-3 text-sm text-muted">Used means a teacher recorded results for it.</p>
    </Widget>
  );
}

export function ResultsReviewWidget({ courseId }: { courseId: number | null }) {
  const summary = useSummary(courseId);
  const rows = (summary.data?.items ?? []).filter((row) => row.accuracy !== null).slice(0, 3);
  return (
    <Widget
      id="dashboard-results"
      title="Results: review these first"
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
            <li key={row.question_id} className="py-2">
              <Link to={`/questions/${row.question_id}`} className="font-bold">
                {row.stem.slice(0, 110)}
                {row.stem.length > 110 ? "…" : ""}
              </Link>
              <p className="flex flex-wrap gap-x-2 text-sm text-muted">
                <code>{row.standard_code}</code>
                <span>{accuracyText(row.correct, row.attempted)}</span>
                {limitedResponses(row.attempted) ? <Pill>Limited response count</Pill> : null}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Widget>
  );
}

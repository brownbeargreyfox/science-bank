import { Link, useSearchParams } from "react-router";
import { useCourses, useCoveragePage } from "../api/queries";
import { accuracyText } from "../lib/results";
import {
  CodeTag,
  Empty,
  ErrorNotice,
  Loading,
  PageHeader,
} from "../components/ui";

const STATUS_ORDER = [
  "generated",
  "reviewed",
  "approved",
  "rejected",
  "archived",
] as const;

export default function CoveragePage() {
  const [params, setParams] = useSearchParams();
  const courses = useCourses();
  const courseId =
    Number(params.get("course")) || courses.data?.[0]?.id || null;
  const yearParam = params.get("year");
  const coverage = useCoveragePage(courseId, yearParam);
  const data = coverage.data;
  const course = courses.data?.find((c) => c.id === courseId);

  const update = (next: Record<string, string | null>) => {
    const merged = new URLSearchParams(params);
    for (const [key, value] of Object.entries(next)) {
      if (value === null) merged.delete(key);
      else merged.set(key, value);
    }
    setParams(merged, { replace: true });
  };

  return (
    <>
      <PageHeader
        title="Coverage"
        lead="Which standards you have assessed in the period you choose, with the questions available for each. This shows what was assessed, not what has been taught."
      />
      <div className="no-print mb-4 flex flex-wrap gap-4">
        <div className="min-w-[14rem]">
          <label htmlFor="cov-course" className="field-label">
            Course
          </label>
          <select
            id="cov-course"
            className="input"
            value={courseId ?? ""}
            onChange={(e) => update({ course: e.target.value })}
          >
            {courses.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.use_year})
              </option>
            ))}
          </select>
        </div>
        <div className="min-w-[14rem]">
          <label htmlFor="cov-year" className="field-label">
            School year
          </label>
          <select
            id="cov-year"
            className="input"
            value={
              data
                ? data.scope.kind === "all_time"
                  ? "all"
                  : String(data.scope.year)
                : (yearParam ?? "")
            }
            onChange={(e) => update({ year: e.target.value })}
            disabled={!data}
          >
            {data?.available_years.map((y) => (
              <option key={y} value={y}>
                {y}-{String((y + 1) % 100).padStart(2, "0")} school year
              </option>
            ))}
            <option value="all">All time</option>
          </select>
        </div>
      </div>

      <ErrorNotice error={coverage.error} />
      {coverage.isPending ? (
        <Loading />
      ) : data ? (
        <>
          <p className="mb-5 text-sm" data-testid="coverage-scope">
            <strong>{data.scope.label}</strong>
            {data.scope.start && data.scope.end ? (
              <span className="text-muted">
                {" "}
                ({data.scope.start} to {data.scope.end})
              </span>
            ) : null}
            <span className="text-muted">
              {" "}
              · {data.summary.standards_assessed} of{" "}
              {data.summary.standards_total} standards assessed in this period.
              Assessed means recorded in an assessment you can see.
            </span>
          </p>
          {data.groups.length === 0 ? (
            <Empty>
              {course?.name ?? "This course"} has no standards in the imported
              data.
            </Empty>
          ) : (
            <div className="space-y-5">
              {data.groups.map((group) => {
                const gid = `cov-${group.bundle_id ?? "other"}`;
                return (
                  <section
                    key={gid}
                    className="panel p-4 sm:p-5"
                    aria-labelledby={gid}
                  >
                    <h2 id={gid} className="text-lg font-bold">
                      {group.name}
                    </h2>
                    <p className="mt-0.5 text-sm text-muted">
                      {group.assessed} of {group.total} standards assessed in
                      this period
                    </p>
                    <ul className="mt-3 divide-y divide-line-soft">
                      {group.standards.map((s) => {
                        const none = STATUS_ORDER.every(
                          (k) => s.questions[k] === 0,
                        );
                        const query = new URLSearchParams({
                          standard: String(s.standard_id),
                        });
                        if (group.bundle_id !== null)
                          query.set("bundle", String(group.bundle_id));
                        if (s.families.length === 1)
                          query.set("family", s.families[0]);
                        return (
                          <li
                            key={s.standard_id}
                            className="grid gap-x-4 gap-y-2 py-3 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)_auto]"
                          >
                            <div className="min-w-0">
                              <CodeTag
                                code={s.code}
                                course={course?.name}
                                to={`/standards/${s.standard_id}`}
                              />
                              <p className="mt-1 line-clamp-3 text-[0.9375rem]">
                                {s.expectation}
                              </p>
                              <p className="mt-1 flex flex-wrap gap-1.5 text-xs">
                                {s.partial ? (
                                  <span className="badge border-line bg-paper text-muted">
                                    Partially addressed
                                  </span>
                                ) : null}
                                {s.also_in.map((name) => (
                                  <span
                                    key={name}
                                    className="badge border-line bg-paper text-muted"
                                  >
                                    Also in {name}
                                  </span>
                                ))}
                              </p>
                            </div>
                            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-4">
                              <div>
                                <dt className="text-xs text-muted">
                                  Times assessed
                                </dt>
                                <dd className="tabular-nums">
                                  {s.times_assessed === 0
                                    ? "Not assessed in this period"
                                    : s.times_assessed}
                                </dd>
                              </div>
                              <div>
                                <dt className="text-xs text-muted">
                                  Last assessed
                                </dt>
                                <dd className="tabular-nums">
                                  {s.last_assessed ?? "—"}
                                </dd>
                              </div>
                              <div>
                                <dt className="text-xs text-muted">Accuracy</dt>
                                <dd className="tabular-nums">
                                  {s.accuracy === null
                                    ? "—"
                                    : accuracyText(s.correct, s.attempted)}
                                  {s.limited_responses ? (
                                    <span className="block text-xs text-muted">
                                      Limited response count
                                    </span>
                                  ) : null}
                                </dd>
                              </div>
                              <div>
                                <dt className="text-xs text-muted">
                                  Questions in bank
                                </dt>
                                <dd>
                                  {none ? (
                                    "No questions in bank"
                                  ) : (
                                    <ul className="text-xs leading-tight tabular-nums">
                                      {STATUS_ORDER.map((k) => (
                                        <li key={k}>
                                          {s.questions[k]} {k}
                                        </li>
                                      ))}
                                    </ul>
                                  )}
                                </dd>
                              </div>
                            </dl>
                            <div className="no-print md:text-right">
                              {s.families.length ? (
                                <Link
                                  to={`/generate?${query}`}
                                  className="btn btn-sm btn-primary"
                                >
                                  Generate
                                  <span className="sr-only"> for {s.code}</span>
                                </Link>
                              ) : (
                                <>
                                  <Link
                                    to={`/standards/${s.standard_id}`}
                                    className="btn btn-sm"
                                  >
                                    View
                                    <span className="sr-only">
                                      {" "}
                                      {s.code} (no question generator yet)
                                    </span>
                                  </Link>
                                  <p className="mt-1 text-xs text-muted">
                                    No question generator yet
                                  </p>
                                </>
                              )}
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                );
              })}
            </div>
          )}
        </>
      ) : null}
    </>
  );
}

import { Link } from "react-router";
import { useAssessments, useCourses, useFamilies, useQuestions } from "../api/queries";
import { STATUSES, STATUS_LABEL } from "../api/types";
import { ErrorNotice, Loading, PageHeader, Section, StatusBadge } from "../components/ui";
import { formatDateTime, pluralize } from "../lib/format";

export default function HomePage() {
  const questions = useQuestions({ page: 1, page_size: 1 });
  const assessments = useAssessments();
  const courses = useCourses();
  const families = useFamilies();

  const counts = questions.data?.status_counts ?? {};
  const total = STATUSES.reduce((n, s) => n + (counts[s] ?? 0), 0);
  const recent = [...(assessments.data ?? [])].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 5);

  return (
    <>
      <PageHeader
        title="Home"
        lead={
          courses.data
            ? `${courses.data.map((c) => c.name).join(", ")} standards for ${courses.data[0]?.use_year ?? ""}.`
            : undefined
        }
        actions={
          <>
            <Link to="/generate" className="btn btn-primary">
              Generate questions
            </Link>
            <Link to="/assessments" className="btn">
              Build an assessment
            </Link>
          </>
        }
      />

      <div className="grid gap-5 lg:grid-cols-[3fr_2fr]">
        <Section title="Question bank" id="home-bank">
          <ErrorNotice error={questions.error} />
          {questions.isPending ? (
            <Loading />
          ) : (
            <>
              <p className="mb-3 text-muted">{pluralize(total, "question")} saved.</p>
              <ul className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                {STATUSES.map((s) => (
                  <li key={s}>
                    <Link
                      to={`/questions?status=${s}`}
                      className="flex h-full flex-col gap-1 rounded-md border border-line px-3 py-2.5 text-ink no-underline hover:border-petrol"
                      aria-label={`${counts[s] ?? 0} ${STATUS_LABEL[s]} questions`}
                    >
                      <span className="text-2xl font-bold tabular-nums">{counts[s] ?? 0}</span>
                      <StatusBadge status={s} />
                    </Link>
                  </li>
                ))}
              </ul>
              {counts.generated ? (
                <p className="mt-3 text-sm">
                  <Link to="/questions?status=generated">Review the {counts.generated} generated questions</Link> before
                  adding them to an assessment.
                </p>
              ) : null}
            </>
          )}
        </Section>

        <Section
          title="Recent assessments"
          id="home-assessments"
          actions={
            <Link to="/assessments" className="text-sm font-bold">
              All assessments
            </Link>
          }
        >
          <ErrorNotice error={assessments.error} />
          {assessments.isPending ? (
            <Loading />
          ) : recent.length === 0 ? (
            <p className="text-muted">
              No assessments yet. <Link to="/assessments">Create one</Link> from reviewed questions.
            </p>
          ) : (
            <ul className="divide-y divide-line-soft">
              {recent.map((a) => (
                <li key={a.id} className="py-2">
                  <Link to={`/assessments/${a.id}`} className="font-bold">
                    {a.title}
                  </Link>
                  <p className="text-sm text-muted">
                    {a.course_name ?? "Any course"}, {pluralize(a.item_count, "item")}, updated{" "}
                    {formatDateTime(a.updated_at)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>

      <Section title="Question families" id="home-families" className="mt-5">
        <p className="mb-3 max-w-[70ch] text-muted">
          Each family builds a fresh data set from a seed and writes questions tied to one standard’s observable
          performances. The same seed always gives the same questions.
        </p>
        {families.data ? (
          <ul className="grid gap-3 md:grid-cols-3">
            {families.data.map((f) => {
              const b = f.bindings[0];
              const sid = b?.standard_ids[0];
              return (
                <li key={f.key} className="rounded-md border border-line p-3">
                  <p className="font-bold">{f.title}</p>
                  <p className="text-sm text-muted">
                    {b ? `${b.code} (${courses.data?.find((c) => c.slug === b.course_slug)?.name ?? b.course_slug}), ` : ""}
                    version {f.version}
                  </p>
                  {sid ? (
                    <Link to={`/generate?standard=${sid}&family=${f.key}`} className="mt-2 inline-block text-sm font-bold">
                      Generate from this family
                    </Link>
                  ) : null}
                </li>
              );
            })}
          </ul>
        ) : (
          <Loading />
        )}
      </Section>
    </>
  );
}

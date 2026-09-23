import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { api, cleanQuery, unwrap } from "../api/client";
import { useCourses, useStandards } from "../api/queries";
import { useQuery } from "@tanstack/react-query";
import { CodeTag, Empty, ErrorNotice, FamilyBadge, Loading, PageHeader, Pill, RepeatBadge } from "../components/ui";
import { useDebounced } from "../lib/hooks";
import { pluralize } from "../lib/format";

export default function StandardsPage() {
  const [params, setParams] = useSearchParams();
  const courses = useCourses();
  const courseId = Number(params.get("course")) || courses.data?.[0]?.id || null;
  const domain = params.get("domain") ?? "";
  const topic = params.get("topic") ?? "";
  const familyOnly = params.get("family") === "1";
  const [q, setQ] = useState(params.get("q") ?? "");
  const debouncedQ = useDebounced(q.trim());

  const update = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    setParams(next, { replace: true });
  };

  useEffect(() => {
    if ((params.get("q") ?? "") === debouncedQ) return;
    const next = new URLSearchParams(params);
    if (debouncedQ) next.set("q", debouncedQ);
    else next.delete("q");
    setParams(next, { replace: true });
  }, [debouncedQ, params, setParams]);

  const all = useStandards({ course_id: courseId }, courseId !== null);
  const results = useStandards(
    { course_id: courseId, q: debouncedQ, domain, topic, with_family_only: familyOnly },
    courseId !== null,
  );
  const topics = useQuery({
    queryKey: ["topics", courseId],
    queryFn: () => unwrap(api.GET("/api/topics", { params: { query: cleanQuery({ course_id: courseId }) } })),
    enabled: courseId !== null,
    staleTime: 5 * 60_000,
  });

  const domains = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of all.data ?? []) m.set(s.domain_code, s.domain_name);
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [all.data]);

  const course = courses.data?.find((c) => c.id === courseId);

  return (
    <>
      <PageHeader
        title="Standards"
        lead="SC Performance Expectations with their official performance targets. Open one to see its boundary, observable performances and source."
        actions={
          <Link to={`/bundles${courseId ? `?course=${courseId}` : ""}`} className="btn">
            View bundles
          </Link>
        }
      />

      <form
        className="panel mb-5 grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-[1.2fr_1.4fr_1fr_1fr]"
        onSubmit={(e) => e.preventDefault()}
        role="search"
        aria-label="Filter standards"
      >
        <div>
          <label htmlFor="std-course" className="field-label">
            Course
          </label>
          <select
            id="std-course"
            className="input"
            value={courseId ?? ""}
            onChange={(e) => update({ course: e.target.value, domain: null, topic: null })}
          >
            {courses.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.use_year})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="std-q" className="field-label">
            Search
          </label>
          <input
            id="std-q"
            type="search"
            className="input"
            placeholder="Code, words in the PE, or a topic"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="std-domain" className="field-label">
            Domain
          </label>
          <select id="std-domain" className="input" value={domain} onChange={(e) => update({ domain: e.target.value })}>
            <option value="">All domains</option>
            {domains.map(([code, name]) => (
              <option key={code} value={code}>
                {code}: {name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="std-topic" className="field-label">
            Topic
          </label>
          <select id="std-topic" className="input" value={topic} onChange={(e) => update({ topic: e.target.value })}>
            <option value="">All topics</option>
            {topics.data?.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 font-bold sm:col-span-2 lg:col-span-4">
          <input
            type="checkbox"
            className="check"
            checked={familyOnly}
            onChange={(e) => update({ family: e.target.checked ? "1" : null })}
          />
          Only standards with a question family
        </label>
      </form>

      <div aria-live="polite" className="mb-2 text-sm text-muted">
        {results.data ? `${pluralize(results.data.length, "standard")} in ${course?.name ?? "this course"}` : ""}
      </div>
      <ErrorNotice error={results.error ?? courses.error} />
      {results.isPending ? (
        <Loading />
      ) : results.data && results.data.length === 0 ? (
        <Empty>No standards match these filters. Clear the search or pick another topic.</Empty>
      ) : (
        <ul className="space-y-3">
          {results.data?.map((s) => (
            <li key={s.id} className="panel p-4">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <CodeTag code={s.code} course={s.course_name} to={`/standards/${s.id}`} />
                <span className="text-sm text-muted">
                  {s.domain_code}: {s.domain_name}
                </span>
                {s.families.length ? <FamilyBadge /> : null}
                {s.repeat_of_biology_1 ? <RepeatBadge /> : null}
              </div>
              <p className="max-w-[75ch]">
                <Link to={`/standards/${s.id}`} className="text-ink no-underline hover:underline">
                  {s.performance_expectation}
                </Link>
              </p>
              {s.topics.length ? (
                <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Topics">
                  {s.topics.map((t) => (
                    <li key={t}>
                      <Pill>{t}</Pill>
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

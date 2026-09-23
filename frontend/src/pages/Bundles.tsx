import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useLocation, useSearchParams } from "react-router";
import { api, unwrap } from "../api/client";
import { useCourses } from "../api/queries";
import { CodeTag, Empty, ErrorNotice, Loading, PageHeader } from "../components/ui";

export default function BundlesPage() {
  const [params, setParams] = useSearchParams();
  const { hash } = useLocation();
  const courses = useCourses();
  const courseId = Number(params.get("course")) || courses.data?.[0]?.id || null;
  const bundles = useQuery({
    queryKey: ["bundles", courseId],
    queryFn: () => unwrap(api.GET("/api/bundles", { params: { query: { course_id: courseId } } })),
    enabled: courseId !== null,
    staleTime: 5 * 60_000,
  });

  useEffect(() => {
    if (hash && bundles.data) document.getElementById(hash.slice(1))?.scrollIntoView();
  }, [hash, bundles.data]);

  const course = courses.data?.find((c) => c.id === courseId);

  return (
    <>
      <PageHeader
        title="Bundles"
        lead="SCDE groups performance expectations into instructional bundles with anchoring phenomena."
      />
      <div className="mb-5 max-w-xs">
        <label htmlFor="b-course" className="field-label">
          Course
        </label>
        <select
          id="b-course"
          className="input"
          value={courseId ?? ""}
          onChange={(e) => setParams({ course: e.target.value }, { replace: true })}
        >
          {courses.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.use_year})
            </option>
          ))}
        </select>
      </div>

      <ErrorNotice error={bundles.error} />
      {bundles.isPending ? (
        <Loading />
      ) : bundles.data?.length === 0 ? (
        <Empty>{course?.name ?? "This course"} has no bundles in the imported data.</Empty>
      ) : (
        <ol className="space-y-5">
          {bundles.data?.map((b, i) => (
            <li key={b.id} id={`bundle-${b.id}`} className="panel scroll-mt-20 p-5">
              <h2 className="text-xl font-bold">
                <span className="mr-2 text-muted tabular-nums">Bundle {i + 1}.</span>
                {b.name}
              </h2>
              <p className="mt-1 text-sm text-muted">From {b.source_document_title}</p>
              {b.narrative ? <p className="mt-3 max-w-[75ch]">{b.narrative}</p> : null}

              <div className="mt-4 grid gap-5 md:grid-cols-2">
                <div>
                  <h3 className="mb-2 font-bold">Aligned performance expectations</h3>
                  <ul className="space-y-2.5">
                    {b.aligned.map((a) => (
                      <li key={a.standard_id}>
                        <div className="flex flex-wrap items-center gap-2">
                          <CodeTag code={a.code} course={b.course_name} to={`/standards/${a.standard_id}`} />
                          {a.partial ? (
                            <span className="badge border-line bg-paper text-muted">Partially addressed</span>
                          ) : null}
                        </div>
                        <p className="mt-1 text-[0.9375rem]">{a.performance_expectation}</p>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="space-y-4">
                  {b.connected_pes.length ? (
                    <div>
                      <h3 className="mb-1 font-bold">Connected PEs</h3>
                      <p className="mb-1 text-sm text-muted">From other courses or grade bands; listed for context.</p>
                      <ul className="flex flex-wrap gap-1.5">
                        {b.connected_pes.map((c) => (
                          <li key={c}>
                            <span className="code-tag">{c}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {b.example_anchoring_phenomena.length ? (
                    <div>
                      <h3 className="mb-1 font-bold">Example anchoring phenomena</h3>
                      <ul className="list-disc space-y-1 pl-5">
                        {b.example_anchoring_phenomena.map((p, j) => (
                          <li key={j}>{p}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
      <p className="mt-6 text-sm">
        <Link to={`/standards${courseId ? `?course=${courseId}` : ""}`}>Back to standards</Link>
      </p>
    </>
  );
}

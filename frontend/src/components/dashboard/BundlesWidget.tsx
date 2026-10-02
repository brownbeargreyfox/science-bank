import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api, unwrap } from "../../api/client";
import { useFamilies } from "../../api/queries";
import { Empty, ErrorNotice, Loading } from "../ui";
import { Widget } from "./Widget";

export function BundlesWidget({ courseId, courseName }: { courseId: number | null; courseName: string }) {
  const families = useFamilies();
  const bundles = useQuery({
    queryKey: ["bundles", courseId],
    queryFn: () => unwrap(api.GET("/api/bundles", { params: { query: { course_id: courseId } } })),
    enabled: courseId !== null,
    staleTime: 5 * 60_000,
  });
  const familyKeys = (standardId: number) =>
    (families.data ?? []).filter((family) => family.bindings.some((binding) => binding.standard_ids.includes(standardId))).map((family) => family.key);

  return <Widget id="dashboard-bundles" title="Bundles" className="lg:col-span-2">
    <ErrorNotice error={bundles.error ?? families.error} />
    {bundles.isPending || families.isPending ? <Loading /> : bundles.data?.length === 0 ? <Empty>{courseName} has no bundles in the imported data.</Empty> :
      <ol className="space-y-4">
        {bundles.data?.map((bundle) => {
          const ready = bundle.aligned.filter((standard) => familyKeys(standard.standard_id).length > 0).length;
          const total = bundle.aligned.length;
          const pct = total ? Math.round((ready / total) * 100) : 0;
          return <li key={bundle.id} className="rounded border border-line-soft p-3">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <Link to={`/bundles?course=${courseId}#bundle-${bundle.id}`} className="font-bold">{bundle.name}</Link>
              <div className="flex min-w-[13rem] flex-1 items-center gap-2 text-sm text-muted">
                <div className="h-1.5 flex-1 overflow-hidden rounded bg-line-soft" role="progressbar" aria-label={`${bundle.name}: ${ready} of ${total} ready to generate`} aria-valuemin={0} aria-valuemax={total} aria-valuenow={ready}>
                  <div className="h-full bg-petrol" style={{ width: `${pct}%` }} />
                </div>
                <span>{ready} of {total} ready to generate</span>
              </div>
              <Link to={`/bundles?course=${courseId}#bundle-${bundle.id}`} className="text-sm font-bold">Open</Link>
            </div>
            <ul className="mt-3 flex flex-wrap gap-2">
              {bundle.aligned.map((standard) => {
                const keys = familyKeys(standard.standard_id);
                const generated = keys.length > 0;
                const query = new URLSearchParams({ standard: String(standard.standard_id), bundle: String(bundle.id) });
                if (keys.length === 1) query.set("family", keys[0]);
                return <li key={standard.standard_id} className="flex items-center gap-1">
                  <Link to={generated ? `/generate?${query}` : `/standards/${standard.standard_id}`} title={standard.performance_expectation} aria-label={generated ? `Generate questions for ${standard.code}` : `View ${standard.code} (no question generator yet)`} className={`btn btn-sm ${generated ? "btn-primary" : ""}`}>
                    <code>{standard.code}</code> · {generated ? "Generate" : "View"}
                  </Link>
                  {!generated ? <span className="text-xs text-muted">No question generator yet</span> : null}
                  {standard.partial ? <span className="badge border-line bg-paper text-muted">Partially addressed</span> : null}
                </li>;
              })}
            </ul>
          </li>;
        })}
      </ol>}
  </Widget>;
}

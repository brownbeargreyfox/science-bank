import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api, unwrap } from "../../api/client";
import { useFamilies } from "../../api/queries";
import { Empty, ErrorNotice, Loading } from "../ui";
import { Widget } from "./Widget";

/**
 * The overview of the course's bundles: one small tile each, with how many of its standards can generate questions.
 * Working with a bundle's standards happens on the Bundles page, which each tile opens.
 */
export function BundlesWidget({ courseId, courseName }: { courseId: number | null; courseName: string }) {
  const families = useFamilies();
  const bundles = useQuery({
    queryKey: ["bundles", courseId],
    queryFn: () => unwrap(api.GET("/api/bundles", { params: { query: { course_id: courseId } } })),
    enabled: courseId !== null,
    staleTime: 5 * 60_000,
  });
  const generatorIds = new Set(
    (families.data ?? []).flatMap((family) => family.bindings.flatMap((binding) => binding.standard_ids)),
  );
  const all = `/bundles?course=${courseId}`;

  return (
    <Widget
      id="dashboard-bundles"
      title="Bundles"
      className="lg:col-span-2"
      actions={
        <Link to={all} className="text-sm font-bold">
          Open bundles
        </Link>
      }
    >
      <ErrorNotice error={bundles.error ?? families.error} />
      {bundles.isPending || families.isPending ? (
        <Loading />
      ) : bundles.data?.length === 0 ? (
        <Empty>{courseName} has no bundles in the imported data.</Empty>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {bundles.data?.map((bundle) => {
            const total = bundle.aligned.length;
            const ready = bundle.aligned.filter((standard) => generatorIds.has(standard.standard_id)).length;
            return (
              <li key={bundle.id}>
                <Link
                  to={`${all}#bundle-${bundle.id}`}
                  className="block h-full border border-line px-3 py-2 text-ink no-underline hover:border-accent hover:bg-accent-soft hover:text-ink"
                >
                  <span className="line-clamp-2 text-sm font-bold">{bundle.name}</span>
                  <span
                    className="my-1.5 block h-1 overflow-hidden bg-line-soft"
                    role="progressbar"
                    aria-label={`${bundle.name}: ${ready} of ${total} ready to generate`}
                    aria-valuemin={0}
                    aria-valuemax={total}
                    aria-valuenow={ready}
                  >
                    <span
                      className="block h-full bg-accent"
                      style={{ width: total ? `${(ready / total) * 100}%` : "0%" }}
                    />
                  </span>
                  <span className="text-xs text-muted">
                    {ready} of {total} ready to generate
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Widget>
  );
}

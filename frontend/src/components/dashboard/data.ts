import { useQuery } from "@tanstack/react-query";
import { api, cleanQuery, unwrap } from "../../api/client";
import { useFamilies, useStandards } from "../../api/queries";

/** Results summary for a course: one row per question that appears in a recorded use (lowest accuracy first). */
export function useSummary(courseId: number | null) {
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

/**
 * How the course's standards divide into three groups that never overlap:
 * used (a teacher recorded results for a question on it), ready (has a question generator, not used yet), and the rest.
 */
export function useCoverage(courseId: number | null) {
  const standards = useStandards({ course_id: courseId }, courseId !== null);
  const families = useFamilies();
  const summary = useSummary(courseId);
  const pending = standards.isPending || families.isPending || summary.isPending;
  const error = standards.error ?? families.error ?? summary.error;
  const all = standards.data ?? [];
  const usedIds = new Set((summary.data?.items ?? []).map((row) => row.standard_id));
  const generatorIds = new Set(
    (families.data ?? []).flatMap((family) => family.bindings.flatMap((binding) => binding.standard_ids)),
  );
  const used = all.filter((standard) => usedIds.has(standard.id)).length;
  const ready = all.filter((standard) => !usedIds.has(standard.id) && generatorIds.has(standard.id)).length;
  return { pending, error, total: all.length, used, ready, rest: Math.max(0, all.length - used - ready) };
}

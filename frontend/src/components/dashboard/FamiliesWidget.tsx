import { Link } from "react-router";
import { useCourses, useFamilies } from "../../api/queries";
import { ErrorNotice, Loading } from "../ui";
import { Widget } from "./Widget";

export function FamiliesWidget({ courseId }: { courseId: number | null }) {
  const families = useFamilies();
  const courses = useCourses();
  const selected = courses.data?.find((course) => course.id === courseId);
  const visible = (families.data ?? []).filter((family) => family.bindings.some((binding) => binding.course_slug === selected?.slug));
  return <Widget id="dashboard-families" title="Question families" className="lg:col-span-2"><p className="mb-3 max-w-[70ch] text-muted">Each family builds a fresh data set from a seed and writes questions tied to one standard’s observable performances. The same seed always gives the same questions.</p><ErrorNotice error={families.error ?? courses.error} />
    {families.isPending || courses.isPending ? <Loading /> : <ul className="grid gap-3 md:grid-cols-3">{visible.map((family) => { const binding = family.bindings.find((item) => item.course_slug === selected?.slug); const standardId = binding?.standard_ids[0]; return <li key={family.key} className="rounded border border-line p-3"><p className="font-bold">{family.title}</p><p className="text-sm text-muted">{binding ? `${binding.code} (${selected?.name ?? binding.course_slug}), ` : ""}version {family.version}</p>{standardId ? <Link to={`/generate?standard=${standardId}&family=${family.key}&course=${courseId}`} className="mt-2 inline-block text-sm font-bold">Generate from this family</Link> : null}</li>; })}</ul>}
  </Widget>;
}

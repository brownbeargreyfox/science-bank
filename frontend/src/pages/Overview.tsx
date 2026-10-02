import { Link, useSearchParams } from "react-router";
import { useCourses } from "../api/queries";
import { Loading, PageHeader } from "../components/ui";
import { BundlesWidget } from "../components/dashboard/BundlesWidget";
import { RecentAssessmentsWidget } from "../components/dashboard/RecentAssessmentsWidget";
import { QuestionBankWidget } from "../components/dashboard/QuestionBankWidget";
import { FamiliesWidget } from "../components/dashboard/FamiliesWidget";
import { ResultsReviewWidget, StandardsCoverageWidget } from "../components/dashboard/ResultsWidgets";

export default function OverviewPage() {
  const courses = useCourses();
  const [params, setParams] = useSearchParams();
  const requested = Number(params.get("course"));
  const course = courses.data?.find((item) => item.id === requested) ?? courses.data?.[0];
  const courseId = course?.id ?? null;
  if (courses.isPending) return <Loading />;
  return <><PageHeader title="Overview" actions={<><Link to={`/generate${courseId ? `?course=${courseId}` : ""}`} className="btn btn-primary">Generate questions</Link><Link to="/assessments" className="btn">New assessment</Link></>} />
    <div className="mb-5 max-w-xs"><label htmlFor="overview-course" className="field-label">Course</label><select id="overview-course" className="input" value={courseId ?? ""} onChange={(event) => setParams({ course: event.target.value }, { replace: true })}>{courses.data?.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.use_year})</option>)}</select></div>
    <div className="grid gap-3 lg:grid-cols-2"><BundlesWidget courseId={courseId} courseName={course?.name ?? "This course"} /><RecentAssessmentsWidget /><QuestionBankWidget courseId={courseId} /><StandardsCoverageWidget courseId={courseId} /><ResultsReviewWidget courseId={courseId} /><FamiliesWidget courseId={courseId} /></div>
  </>;
}

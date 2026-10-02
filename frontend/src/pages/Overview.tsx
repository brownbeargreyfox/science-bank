import { Link, useSearchParams } from "react-router";
import { useCourses } from "../api/queries";
import { BundlesWidget } from "../components/dashboard/BundlesWidget";
import { KpiTiles } from "../components/dashboard/KpiTiles";
import { RecentAssessmentsWidget } from "../components/dashboard/RecentAssessmentsWidget";
import { ResultsReviewWidget, StandardsCoverageWidget } from "../components/dashboard/ResultsWidgets";
import { Empty, ErrorNotice, Loading, PageHeader } from "../components/ui";

/** A short, top-level view of one course. The places to work (bundles, generating, assessing) are one click away. */
export default function OverviewPage() {
  const courses = useCourses();
  const [params, setParams] = useSearchParams();
  const requested = Number(params.get("course"));
  const course = courses.data?.find((item) => item.id === requested) ?? courses.data?.[0];
  const courseId = course?.id ?? null;
  if (courses.isPending) return <Loading />;
  if (courses.error) return <ErrorNotice error={courses.error} title="Courses could not be loaded." />;
  if (!course) return <Empty>No courses have been imported yet.</Empty>;
  return (
    <>
      <PageHeader
        title="Overview"
        actions={
          <>
            <div className="flex items-center gap-2">
              <label htmlFor="overview-course" className="text-sm font-bold">
                Course
              </label>
              <select
                id="overview-course"
                className="input w-auto"
                value={course.id}
                onChange={(event) => setParams({ course: event.target.value }, { replace: true })}
              >
                {courses.data?.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} ({item.use_year})
                  </option>
                ))}
              </select>
            </div>
            <Link to={`/generate?course=${course.id}`} className="btn">
              Generate questions
            </Link>
            <Link to="/assessments" className="btn btn-primary">
              New assessment
            </Link>
          </>
        }
      />
      <KpiTiles courseId={courseId} />
      <div className="grid gap-3 lg:grid-cols-2">
        <BundlesWidget courseId={courseId} courseName={course.name} />
        <RecentAssessmentsWidget />
        <ResultsReviewWidget courseId={courseId} />
        <StandardsCoverageWidget courseId={courseId} />
      </div>
    </>
  );
}

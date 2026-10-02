import { Link } from "react-router";
import { useAssessments } from "../../api/queries";
import { ErrorNotice, Loading } from "../ui";
import { formatDateTime, pluralize } from "../../lib/format";
import { Widget } from "./Widget";

export function RecentAssessmentsWidget() {
  const assessments = useAssessments();
  const recent = [...(assessments.data ?? [])].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 5);
  return (
    <Widget
      id="dashboard-assessments"
      title="Recent assessments"
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
          {recent.map((assessment) => (
            <li key={assessment.id} className="py-2">
              <Link to={`/assessments/${assessment.id}`} className="font-bold">
                {assessment.title}
              </Link>
              <p className="text-sm text-muted">
                {assessment.course_name ?? "Any course"}, {pluralize(assessment.item_count, "item")}, updated{" "}
                {formatDateTime(assessment.updated_at)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Widget>
  );
}

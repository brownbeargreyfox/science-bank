import { Link } from "react-router";
import { useQuestions } from "../../api/queries";
import { STATUSES, STATUS_LABEL } from "../../api/types";
import { ErrorNotice, Loading, StatusBadge } from "../ui";
import { Widget } from "./Widget";

export function QuestionBankWidget({ courseId }: { courseId: number | null }) {
  const questions = useQuestions({ course_id: courseId, page: 1, page_size: 1 });
  const counts = questions.data?.status_counts ?? {};
  return (
    <Widget id="dashboard-bank" title="Question bank">
      <ErrorNotice error={questions.error} />
      {questions.isPending ? (
        <Loading />
      ) : (
        <>
          <ul className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            {STATUSES.map((status) => (
              <li key={status}>
                <Link
                  to={`/questions?status=${status}&course=${courseId ?? ""}`}
                  className="flex h-full flex-col gap-1 rounded border border-line px-2 py-2 text-ink no-underline hover:border-petrol"
                  aria-label={`${counts[status] ?? 0} ${STATUS_LABEL[status]} questions`}
                >
                  <span className="text-xl font-bold tabular-nums">{counts[status] ?? 0}</span>
                  <StatusBadge status={status} />
                </Link>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-sm">
            {counts.generated ? (
              <>
                <Link to={`/questions?status=generated&course=${courseId ?? ""}`}>
                  Review the {counts.generated} generated questions
                </Link>{" "}
                before adding them to an assessment.
              </>
            ) : (
              "Review generated questions before adding them to an assessment."
            )}
          </p>
        </>
      )}
    </Widget>
  );
}

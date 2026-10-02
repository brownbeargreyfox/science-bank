import { Link } from "react-router";
import { useAssessments, useQuestions } from "../../api/queries";
import { STATUSES } from "../../api/types";
import { useCoverage } from "./data";

function Tile({
  to,
  value,
  label,
  tone = "accent",
}: {
  to: string;
  value: string;
  label: string;
  tone?: "accent" | "bound";
}) {
  return (
    <li>
      <Link
        to={to}
        className={`block h-full border border-line bg-surface px-3 py-2 text-ink no-underline hover:border-accent hover:text-ink ${
          tone === "bound" ? "border-t-[3px] border-t-bound" : "border-t-[3px] border-t-accent"
        }`}
      >
        <span className="block text-2xl font-bold tabular-nums leading-tight">{value}</span>
        <span className="text-sm text-muted">{label}</span>
      </Link>
    </li>
  );
}

/** The four numbers a teacher wants at a glance. Each is a link into the place that explains it. */
export function KpiTiles({ courseId }: { courseId: number | null }) {
  const questions = useQuestions({ course_id: courseId, page: 1, page_size: 1 });
  const assessments = useAssessments();
  const coverage = useCoverage(courseId);
  const counts = questions.data?.status_counts ?? {};
  const total = STATUSES.reduce((n, status) => n + (counts[status] ?? 0), 0);
  const dash = "–";
  const course = courseId ? `&course=${courseId}` : "";
  return (
    <ul className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="Summary">
      <Tile to={`/questions?${course.slice(1)}`} value={questions.data ? String(total) : dash} label="Questions" />
      <Tile
        to={`/questions?status=generated${course}`}
        value={questions.data ? String(counts.generated ?? 0) : dash}
        label="To review"
        tone="bound"
      />
      <Tile to="/assessments" value={assessments.data ? String(assessments.data.length) : dash} label="Assessments" />
      <Tile
        to="/results"
        value={coverage.pending || coverage.error ? dash : `${coverage.used} of ${coverage.total}`}
        label="Standards in use"
      />
    </ul>
  );
}

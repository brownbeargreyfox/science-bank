import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { api, unwrap } from "../api/client";
import { queryClient, useAssessments, useCourses } from "../api/queries";
import { Empty, ErrorNotice, Loading, PageHeader, Section } from "../components/ui";
import { formatDateTime, pluralize } from "../lib/format";

export default function AssessmentsPage() {
  const [showDeleted, setShowDeleted] = useState(false);
  const assessments = useAssessments(showDeleted);
  const courses = useCourses();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [courseId, setCourseId] = useState("");
  const [instructions, setInstructions] = useState("");

  const create = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/assessments", {
          body: { title: title.trim(), course_id: courseId ? Number(courseId) : null, instructions },
        }),
      ),
    onSuccess: (a) => {
      void queryClient.invalidateQueries({ queryKey: ["assessments"] });
      navigate(`/assessments/${a.id}`);
    },
  });

  const restore = useMutation({
    mutationFn: (id: number) =>
      unwrap(api.POST("/api/assessments/{assessment_id}/restore", { params: { path: { assessment_id: id } } })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["assessments"] }),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (title.trim()) create.mutate();
  };

  const list = [...(assessments.data ?? [])].sort((a, b) => b.updated_at.localeCompare(a.updated_at));

  return (
    <>
      <PageHeader title="Assessments" lead="Quizzes and tests built from questions in the bank, ready to print." />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <section aria-labelledby="list-h" className="min-w-0">
          <h2 id="list-h" className="sr-only">
            Your assessments
          </h2>
          <div className="mb-3 flex justify-end">
            <label className="flex items-center gap-2 text-sm font-bold">
              <input type="checkbox" className="check" checked={showDeleted} onChange={(e) => setShowDeleted(e.target.checked)} />
              Show deleted
            </label>
          </div>
          <ErrorNotice error={assessments.error ?? restore.error} />
          {assessments.isPending ? (
            <Loading />
          ) : list.length === 0 ? (
            <Empty>No assessments yet. Create one with the form.</Empty>
          ) : (
            <ul className="panel divide-y divide-line-soft">
              {list.map((a) => (
                <li
                  key={a.id}
                  className={`flex flex-wrap items-center justify-between gap-3 p-4 ${a.deleted_at ? "bg-paper text-muted" : ""}`}
                >
                  <div className="min-w-0">
                    {a.deleted_at ? (
                      <span className="text-lg font-bold">{a.title}</span>
                    ) : (
                      <Link to={`/assessments/${a.id}`} className="text-lg font-bold">
                        {a.title}
                      </Link>
                    )}
                    <p className="text-sm text-muted">
                      {a.course_name ?? "Any course"}, {pluralize(a.item_count, "question")}, by {a.owner.username},{" "}
                      {a.deleted_at ? `deleted ${formatDateTime(a.deleted_at)}` : `updated ${formatDateTime(a.updated_at)}`}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    {a.deleted_at ? (
                      <button
                        type="button"
                        className="btn btn-sm"
                        disabled={restore.isPending}
                        onClick={() => restore.mutate(a.id)}
                      >
                        Restore
                      </button>
                    ) : (
                      <>
                        <Link to={`/assessments/${a.id}/print/student`} className="btn btn-sm">
                          Student copy
                        </Link>
                        <Link to={`/assessments/${a.id}/print/teacher`} className="btn btn-sm">
                          Answer key
                        </Link>
                      </>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <Section title="New assessment" id="new-h">
          <form onSubmit={submit} className="space-y-3">
            <div>
              <label htmlFor="na-title" className="field-label">
                Title
              </label>
              <input
                id="na-title"
                className="input"
                value={title}
                required
                placeholder="Unit 4 quiz: heredity"
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="na-course" className="field-label">
                Course <span className="font-normal text-muted">(optional)</span>
              </label>
              <select id="na-course" className="input" value={courseId} onChange={(e) => setCourseId(e.target.value)}>
                <option value="">Any course</option>
                {courses.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.use_year})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="na-instr" className="field-label">
                Instructions for students <span className="font-normal text-muted">(optional)</span>
              </label>
              <textarea
                id="na-instr"
                className="input"
                rows={3}
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
              />
            </div>
            <div aria-live="polite">
              <ErrorNotice error={create.error} />
            </div>
            <button type="submit" className="btn btn-primary" disabled={!title.trim() || create.isPending}>
              {create.isPending ? "Creating…" : "Create assessment"}
            </button>
          </form>
        </Section>
      </div>
    </>
  );
}

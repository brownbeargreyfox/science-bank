import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useParams } from "react-router";
import { api, unwrap } from "../api/client";
import type { PrintQuestion } from "../api/types";
import { QuestionBody } from "../components/QuestionBody";
import { Stimulus } from "../components/Stimulus";
import { ErrorNotice, Loading } from "../components/ui";
import { parsePrintStandards } from "../lib/format";

function PrintItem({ q, teacher }: { q: PrintQuestion; teacher: boolean }) {
  // The student copy never renders keys, even if a payload carried them.
  const choices = teacher
    ? q.choices
    : q.choices.map((c) => ({ label: c.label, text: c.text }));
  return (
    <div className={`py-3 ${teacher ? "print-question-key" : "print-question"}`}>
      <QuestionBody
        number={q.number}
        stem={q.stem}
        questionType={q.question_type}
        choices={choices}
        answer={teacher ? q.answer : null}
        explanation={teacher ? q.explanation : null}
        showKey={teacher}
        answerLines={!teacher && q.question_type === "constructed_response" ? 7 : 0}
        meta={
          teacher ? (
            <p className="mt-1 font-sans text-sm text-muted print:text-black">
              {q.standard_code}, DOK {q.dok}
              {q.teacher_edited ? ". Teacher-edited: this key reflects your edits, not the engine’s." : ""}
            </p>
          ) : null
        }
      />
    </div>
  );
}

export default function PrintPage() {
  const { id: idParam, variant: variantParam } = useParams();
  const id = Number(idParam);
  const variant = variantParam === "teacher" ? "teacher" : "student";
  const teacher = variant === "teacher";

  const q = useQuery({
    queryKey: ["print", id, variant],
    queryFn: () =>
      unwrap(
        api.GET("/api/assessments/{assessment_id}/print", {
          params: { path: { assessment_id: id }, query: { variant } },
        }),
      ),
    enabled: Number.isFinite(id),
  });

  useEffect(() => {
    if (q.data) document.title = `${q.data.title} (${teacher ? "answer key" : "student copy"})`;
    return () => {
      document.title = "Science Bank";
    };
  }, [q.data, teacher]);

  const standards = parsePrintStandards(q.data?.standards);

  return (
    <div className="min-h-screen bg-paper print:bg-white">
      <div className="no-print sticky top-0 z-10 border-b border-line bg-surface">
        <div className="mx-auto flex max-w-[8.5in] flex-wrap items-center justify-between gap-2 px-4 py-2.5">
          <Link to={`/assessments/${id}`} className="font-bold">
            Back to assessment
          </Link>
          <div className="flex flex-wrap gap-2">
            <Link to={`/assessments/${id}/print/${teacher ? "student" : "teacher"}`} className="btn btn-sm">
              {teacher ? "Student copy" : "Answer key"}
            </Link>
            <button type="button" className="btn btn-primary btn-sm" onClick={() => window.print()} disabled={!q.data}>
              Print
            </button>
          </div>
        </div>
      </div>

      <main className="print-sheet mx-auto my-6 max-w-[8.5in] bg-white px-5 py-6 text-black shadow-[0_0_0_1px_#c9d3d4] sm:px-12 sm:py-10">
        {q.isPending ? <Loading /> : null}
        <ErrorNotice error={q.error} title="The print view could not be loaded." />
        {q.data ? (
          <>
            <header className="mb-5 border-b-2 border-black pb-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h1 className="booklet text-2xl font-semibold">{q.data.title}</h1>
                <p className="text-sm font-bold">
                  {teacher ? "Answer key" : q.data.course_name ?? ""}
                </p>
              </div>
              {teacher ? (
                <p className="text-sm">
                  {q.data.course_name ? `${q.data.course_name}. ` : ""}
                  {q.data.question_count} questions. Correct choices are marked ✓ with a box.
                </p>
              ) : (
                <div className="mt-4 grid grid-cols-[1fr_auto_auto] gap-x-6 gap-y-2 text-[0.95rem]">
                  <p className="flex items-end gap-2">
                    Name <span className="inline-block min-w-0 flex-1 border-b border-black" />
                  </p>
                  <p className="flex items-end gap-2">
                    Date <span className="inline-block w-24 border-b border-black" />
                  </p>
                  <p className="flex items-end gap-2">
                    Period <span className="inline-block w-12 border-b border-black" />
                  </p>
                </div>
              )}
            </header>

            {q.data.instructions ? (
              <section className="mb-5" aria-label="Instructions">
                <p className="booklet whitespace-pre-line">
                  <span className="font-semibold">Instructions: </span>
                  {q.data.instructions}
                </p>
              </section>
            ) : null}

            {q.data.blocks.map((b, bi) => {
              const [first, ...rest] = b.questions;
              return (
                <section key={bi} className="mb-4" aria-label={b.stimulus_title ?? `Question ${first?.number ?? ""}`}>
                  {b.stimulus ? (
                    <>
                      {b.questions.length > 1 ? (
                        <p className="keep-with-next mb-1 font-sans text-sm font-bold">
                          Use the information below to answer questions {first?.number}–
                          {b.questions[b.questions.length - 1].number}.
                        </p>
                      ) : null}
                      {/*
                        Long stimuli can't fit on one page with their first question, so rather
                        than one unbreakable block, tables/figures/questions each stay whole and
                        break-after: avoid keeps question 1 on the page where the stimulus ends.
                      */}
                      <div className="keep-with-next border-y-2 border-black py-3">
                        <Stimulus body={b.stimulus} level={2} />
                      </div>
                      {first ? <PrintItem q={first} teacher={teacher} /> : null}
                      {rest.map((pq) => (
                        <PrintItem key={pq.number} q={pq} teacher={teacher} />
                      ))}
                    </>
                  ) : (
                    b.questions.map((pq) => <PrintItem key={pq.number} q={pq} teacher={teacher} />)
                  )}
                </section>
              );
            })}

            {teacher && standards.length ? (
              <section className="keep mt-6 border-t-2 border-black pt-3" aria-labelledby="std-h">
                <h2 id="std-h" className="mb-2 text-lg font-bold">
                  Standards assessed
                </h2>
                <ul className="space-y-2 text-[0.95rem]">
                  {standards.map((s) => (
                    <li key={`${s.code}-${s.course}`}>
                      <span className="font-bold">
                        {s.code} ({s.course}
                        {s.use_year ? `, ${s.use_year}` : ""})
                      </span>
                      {s.performance_expectation ? `: ${s.performance_expectation}` : ""}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </>
        ) : null}
      </main>
    </div>
  );
}

import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { api, unwrap } from "../api/client";
import { fetchQuestions, queryClient, useCourses, useQuestions } from "../api/queries";
import {
  TYPE_LABEL,
  type AddItemsOut,
  type AssessmentDetail,
  type QuestionSummary,
  type QuestionType,
  type Status,
} from "../api/types";
import { SkippedList } from "../components/AddToAssessment";
import {
  CodeTag,
  DokBadge,
  Empty,
  ErrorNotice,
  Loading,
  Notice,
  PageHeader,
  Section,
  StatusBadge,
  TypeBadge,
} from "../components/ui";
import { parseCoverage, pluralize } from "../lib/format";
import { useDebounced } from "../lib/hooks";

type Key = readonly unknown[];

function DetailsForm({ a }: { a: AssessmentDetail }) {
  const courses = useCourses();
  const [title, setTitle] = useState(a.title);
  const [courseId, setCourseId] = useState(a.course_id ? String(a.course_id) : "");
  const [instructions, setInstructions] = useState(a.instructions);
  const dirty =
    title !== a.title || courseId !== (a.course_id ? String(a.course_id) : "") || instructions !== a.instructions;

  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.PATCH("/api/assessments/{assessment_id}", {
          params: { path: { assessment_id: a.id } },
          body: { title: title.trim(), course_id: courseId ? Number(courseId) : null, instructions },
        }),
      ),
    onSuccess: (updated) => {
      queryClient.setQueryData(["assessment", a.id], updated);
      void queryClient.invalidateQueries({ queryKey: ["assessments"] });
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (title.trim() && dirty) save.mutate();
  };

  return (
    <form onSubmit={submit} className="panel grid gap-3 p-4 sm:grid-cols-[2fr_1fr] sm:p-5">
      <div>
        <label htmlFor="ab-title" className="field-label">
          Title
        </label>
        <input id="ab-title" className="input text-lg font-bold" value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>
      <div>
        <label htmlFor="ab-course" className="field-label">
          Course
        </label>
        <select id="ab-course" className="input" value={courseId} onChange={(e) => setCourseId(e.target.value)}>
          <option value="">Any course</option>
          {courses.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.use_year})
            </option>
          ))}
        </select>
      </div>
      <div className="sm:col-span-2">
        <label htmlFor="ab-instr" className="field-label">
          Instructions for students
        </label>
        <textarea id="ab-instr" className="input" rows={2} value={instructions} onChange={(e) => setInstructions(e.target.value)} />
      </div>
      <div className="flex flex-wrap items-center gap-3 sm:col-span-2" aria-live="polite">
        <button type="submit" className="btn btn-primary btn-sm" disabled={!dirty || !title.trim() || save.isPending}>
          {save.isPending ? "Saving…" : "Save details"}
        </button>
        {dirty ? <span className="text-sm text-bound">Unsaved changes</span> : save.isSuccess ? <span className="text-sm text-ok">Details saved.</span> : null}
        <ErrorNotice error={save.error} />
      </div>
    </form>
  );
}

function Summary({ a }: { a: AssessmentDetail }) {
  const coverage = parseCoverage(a.standards_coverage);
  const doks = [1, 2, 3, 4].map((d) => ({ d, n: a.dok_distribution[String(d)] ?? 0 }));
  const max = Math.max(1, ...doks.map((x) => x.n));
  return (
    <Section title="Summary" id="sum-h">
      <h3 className="mb-1 font-bold">Depth of Knowledge</h3>
      <dl className="mb-4 space-y-1">
        {doks.map(({ d, n }) => (
          <div key={d} className="grid grid-cols-[3.5rem_1fr_2rem] items-center gap-2 text-sm">
            <dt>DOK {d}</dt>
            <dd className="h-3 rounded-sm bg-line-soft" aria-hidden="true">
              <div className="h-3 rounded-sm bg-petrol" style={{ width: `${(n / max) * 100}%` }} />
            </dd>
            <dd className="text-right tabular-nums">{n}</dd>
          </div>
        ))}
      </dl>
      <h3 className="mb-1 font-bold">Question types</h3>
      <ul className="mb-4 text-sm">
        {(Object.keys(TYPE_LABEL) as QuestionType[]).map((t) => (
          <li key={t}>
            {TYPE_LABEL[t]}: <span className="tabular-nums font-bold">{a.question_type_counts[t] ?? 0}</span>
          </li>
        ))}
      </ul>
      <h3 className="mb-1 font-bold">Standards covered</h3>
      {coverage.length === 0 ? (
        <p className="text-sm text-muted">None yet.</p>
      ) : (
        <ul className="space-y-2 text-sm">
          {coverage.map((c) => (
            <li key={`${c.standard_id ?? c.code}-${c.course}`}>
              <span className="flex flex-wrap items-center gap-2">
                <CodeTag code={c.code} course={c.course} to={c.standard_id ? `/standards/${c.standard_id}` : undefined} />
                <span className="text-muted">{pluralize(c.count ?? 0, "question")}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

const STATUS_CHOICES: { value: string; label: string; statuses: Status[] }[] = [
  { value: "ar", label: "Approved and reviewed", statuses: ["approved", "reviewed"] },
  { value: "approved", label: "Approved only", statuses: ["approved"] },
  { value: "reviewed", label: "Reviewed only", statuses: ["reviewed"] },
  { value: "generated", label: "Generated (not yet reviewed)", statuses: ["generated"] },
  { value: "any", label: "Any status", statuses: [] },
];

function AddPanel({ a, onAdded }: { a: AssessmentDetail; onAdded: (out: AddItemsOut) => void }) {
  const [statusKey, setStatusKey] = useState("ar");
  const [courseFilter, setCourseFilter] = useState<string>(a.course_id ? String(a.course_id) : "");
  const [search, setSearch] = useState("");
  const q = useDebounced(search.trim());
  const [page, setPage] = useState(1);
  const courses = useCourses();
  const statuses = STATUS_CHOICES.find((s) => s.value === statusKey)?.statuses ?? [];

  const results = useQuestions({
    status: statuses,
    course_id: courseFilter ? Number(courseFilter) : null,
    q: q || null,
    page,
    page_size: 30,
  });
  const inAssessment = useMemo(() => new Set(a.items.map((i) => i.question_id)), [a.items]);

  const add = useMutation({
    mutationFn: (ids: number[]) =>
      unwrap(
        api.POST("/api/assessments/{assessment_id}/items", {
          params: { path: { assessment_id: a.id } },
          body: { question_ids: ids },
        }),
      ),
    onSuccess: onAdded,
  });

  const addStimulus = useMutation({
    mutationFn: async (stimulusId: number) => {
      const all = await fetchQuestions({ stimulus_id: stimulusId, status: statuses, page_size: 200 });
      const ids = all.items.map((i) => i.id).filter((id) => !inAssessment.has(id));
      if (!ids.length) return { added: [], skipped: {} } as AddItemsOut;
      return unwrap(
        api.POST("/api/assessments/{assessment_id}/items", {
          params: { path: { assessment_id: a.id } },
          body: { question_ids: ids },
        }),
      );
    },
    onSuccess: onAdded,
  });

  // Group results by stimulus so a shared data set is added together.
  const groups = useMemo(() => {
    const out: { key: string; stimulusId: number | null; title: string | null; items: QuestionSummary[] }[] = [];
    for (const it of results.data?.items ?? []) {
      const key = it.stimulus_id ? `s${it.stimulus_id}` : `q${it.id}`;
      const g = out.find((x) => x.key === key);
      if (g) g.items.push(it);
      else out.push({ key, stimulusId: it.stimulus_id, title: it.stimulus_title, items: [it] });
    }
    return out;
  }, [results.data]);

  const total = results.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / 30));
  const busy = add.isPending || addStimulus.isPending;

  return (
    <Section title="Add questions" id="add-h">
      <div className="mb-3 grid gap-3 sm:grid-cols-3">
        <div>
          <label htmlFor="ap-status" className="field-label">
            Status
          </label>
          <select id="ap-status" className="input" value={statusKey} onChange={(e) => {
              setStatusKey(e.target.value);
              setPage(1);
            }}>
            {STATUS_CHOICES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="ap-course" className="field-label">
            Course
          </label>
          <select id="ap-course" className="input" value={courseFilter} onChange={(e) => {
              setCourseFilter(e.target.value);
              setPage(1);
            }}>
            <option value="">All courses</option>
            {courses.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="ap-q" className="field-label">
            Search
          </label>
          <input id="ap-q" type="search" className="input" value={search} onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }} />
        </div>
      </div>
      <div aria-live="polite">
        <ErrorNotice error={add.error ?? addStimulus.error} title="Nothing was added." />
        <p className="mb-2 text-sm text-muted">{results.data ? `${pluralize(total, "question")} found` : ""}</p>
      </div>
      <ErrorNotice error={results.error} />
      {results.isPending ? (
        <Loading />
      ) : groups.length === 0 ? (
        <Empty>
          No {statusKey === "any" ? "" : `${STATUS_CHOICES.find((s) => s.value === statusKey)?.label.toLowerCase()} `}
          questions match. Approve questions in the <Link to="/questions">question bank</Link>, or change the status
          filter.
        </Empty>
      ) : (
        <ul className="space-y-3">
          {groups.map((g) => (
            <li key={g.key} className={g.stimulusId ? "rounded-md border border-line" : ""}>
              {g.stimulusId ? (
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line-soft bg-paper px-3 py-2">
                  <p className="min-w-0 text-sm">
                    <span className="text-muted">Stimulus: </span>
                    <span className="font-bold">{g.title}</span>
                  </p>
                  <button
                    type="button"
                    className="btn btn-sm"
                    disabled={busy}
                    onClick={() => addStimulus.mutate(g.stimulusId as number)}
                  >
                    Add all from this stimulus
                  </button>
                </div>
              ) : null}
              <ul className="divide-y divide-line-soft">
                {g.items.map((it) => {
                  const added = inAssessment.has(it.id);
                  return (
                    <li key={it.id} className="flex items-start gap-3 px-3 py-2.5">
                      <div className="min-w-0 flex-1">
                        <p className="booklet line-clamp-2 text-[0.975rem]">{it.stem}</p>
                        <p className="mt-1 flex flex-wrap items-center gap-1.5 text-sm">
                          <CodeTag code={it.standard_code} course={it.course_name} />
                          <DokBadge dok={it.dok} />
                          <TypeBadge type={it.question_type} short />
                          <StatusBadge status={it.status} />
                          <Link to={`/questions/${it.id}`} className="text-sm">
                            Open
                          </Link>
                        </p>
                      </div>
                      <button
                        type="button"
                        className="btn btn-sm flex-none"
                        disabled={added || busy}
                        onClick={() => add.mutate([it.id])}
                        aria-label={added ? `Question ${it.id} already added` : `Add question ${it.id}`}
                      >
                        {added ? "Added" : "Add"}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
        </ul>
      )}
      {pages > 1 ? (
        <nav aria-label="Result pages" className="mt-3 flex items-center justify-between gap-2">
          <button type="button" className="btn btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Previous
          </button>
          <span className="text-sm text-muted">
            Page {page} of {pages}
          </span>
          <button type="button" className="btn btn-sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>
            Next
          </button>
        </nav>
      ) : null}
    </Section>
  );
}

export default function AssessmentBuilderPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const key: Key = ["assessment", id];
  const q = useQuery({
    queryKey: key,
    queryFn: () => unwrap(api.GET("/api/assessments/{assessment_id}", { params: { path: { assessment_id: id } } })),
    enabled: Number.isFinite(id),
  });
  const [addResult, setAddResult] = useState<AddItemsOut | null>(null);
  const [live, setLive] = useState("");
  const focusAfterMove = useRef<{ itemId: number; dir: "up" | "down" } | null>(null);

  const setData = (d: AssessmentDetail) => {
    queryClient.setQueryData(key, d);
    void queryClient.invalidateQueries({ queryKey: ["assessments"] });
  };

  const reorder = useMutation({
    mutationFn: (ids: number[]) =>
      unwrap(
        api.PUT("/api/assessments/{assessment_id}/items/order", {
          params: { path: { assessment_id: id } },
          body: { item_ids: ids },
        }),
      ),
    onSuccess: setData,
  });
  // After a move, keep keyboard focus on the moved item (its other arrow if this one is now disabled).
  useEffect(() => {
    const f = focusAfterMove.current;
    if (!f || reorder.isPending) return;
    focusAfterMove.current = null;
    const other = f.dir === "up" ? "down" : "up";
    const btn = document.getElementById(`mv-${f.dir}-${f.itemId}`) as HTMLButtonElement | null;
    const alt = document.getElementById(`mv-${other}-${f.itemId}`) as HTMLButtonElement | null;
    (btn && !btn.disabled ? btn : alt)?.focus();
  }, [q.data, reorder.isPending]);

  const remove = useMutation({
    mutationFn: (itemId: number) =>
      unwrap(
        api.DELETE("/api/assessments/{assessment_id}/items/{item_id}", {
          params: { path: { assessment_id: id, item_id: itemId } },
        }),
      ),
    onSuccess: (d) => {
      setData(d);
      setLive("Question removed.");
      void queryClient.invalidateQueries({ queryKey: ["question"] });
    },
  });
  const refresh = useMutation({
    mutationFn: (itemId: number) =>
      unwrap(
        api.POST("/api/assessments/{assessment_id}/items/{item_id}/refresh", {
          params: { path: { assessment_id: id, item_id: itemId } },
        }),
      ),
    onSuccess: (d) => {
      setData(d);
      setLive("Now using the latest version.");
    },
  });
  const del = useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/assessments/{assessment_id}", { params: { path: { assessment_id: id } } })),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: key });
      void queryClient.invalidateQueries({ queryKey: ["assessments"] });
      void queryClient.invalidateQueries({ queryKey: ["question"] });
      navigate("/assessments");
    },
  });

  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorNotice error={q.error} title="This assessment could not be loaded." />;
  const a = q.data;
  const items = [...a.items].sort((x, y) => x.position - y.position);

  const move = (index: number, delta: number) => {
    const target = index + delta;
    if (target < 0 || target >= items.length) return;
    const ids = items.map((i) => i.id);
    [ids[index], ids[target]] = [ids[target], ids[index]];
    focusAfterMove.current = { itemId: items[index].id, dir: delta < 0 ? "up" : "down" };
    reorder.mutate(ids, {
      onSuccess: () => setLive(`Question moved to position ${target + 1}.`),
    });
  };

  const busy = reorder.isPending || remove.isPending || refresh.isPending;
  const outdated = items.filter((i) => i.pinned_version_no < i.latest_version_no).length;
  const notApproved = items.filter((i) => i.question_status !== "approved").length;

  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-3 text-sm">
        <Link to="/assessments">Assessments</Link>
      </nav>
      <PageHeader
        title={a.title}
        lead={`${a.course_name ?? "Any course"}, ${pluralize(a.item_count, "question")}`}
        actions={
          <>
            <Link to={`/assessments/${a.id}/print/student`} className="btn btn-primary">
              Print student copy
            </Link>
            <Link to={`/assessments/${a.id}/print/teacher`} className="btn">
              Print answer key
            </Link>
          </>
        }
      />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="min-w-0 space-y-5">
          <DetailsForm key={a.id} a={a} />

          <Section title="Questions" id="items-h">
            <p className="sr-only" aria-live="polite">
              {live}
            </p>
            <div aria-live="polite" className="space-y-2">
              <ErrorNotice error={reorder.error ?? remove.error ?? refresh.error} />
              {addResult ? (
                <Notice tone={Object.keys(addResult.skipped).length ? "warn" : "ok"}>
                  <p>Added {pluralize(addResult.added.length, "question")}.</p>
                  <SkippedList skipped={addResult.skipped} />
                </Notice>
              ) : null}
            </div>
            {outdated || notApproved ? (
              <p className="my-2 text-sm text-bound">
                {outdated ? `${pluralize(outdated, "question")} ha${outdated === 1 ? "s" : "ve"} a newer version. ` : ""}
                {notApproved ? `${pluralize(notApproved, "question")} ${notApproved === 1 ? "is" : "are"} not approved yet.` : ""}
              </p>
            ) : null}
            {items.length === 0 ? (
              <Empty>No questions yet. Add some from the panel below.</Empty>
            ) : (
              <ol className="mt-2 divide-y divide-line-soft">
                {items.map((it, i) => {
                  const prev = items[i - 1];
                  const sameStim = it.stimulus_id !== null && prev?.stimulus_id === it.stimulus_id;
                  const stale = it.pinned_version_no < it.latest_version_no;
                  return (
                    <li key={it.id} className={`flex gap-3 py-3 ${sameStim ? "border-l-4 border-l-line pl-2" : ""}`}>
                      <span className="w-7 flex-none pt-0.5 text-right font-bold tabular-nums">{i + 1}.</span>
                      <div className="min-w-0 flex-1">
                        {it.stimulus_title && !sameStim ? (
                          <p className="mb-1 text-sm text-muted">
                            Stimulus: <span className="font-bold text-ink">{it.stimulus_title}</span>
                          </p>
                        ) : null}
                        <Link to={`/questions/${it.question_id}`} className="booklet line-clamp-2 text-ink no-underline hover:underline">
                          {it.stem}
                        </Link>
                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-sm">
                          <CodeTag code={it.standard_code} course={it.course_name} />
                          <DokBadge dok={it.dok} />
                          <TypeBadge type={it.question_type} short />
                          <StatusBadge status={it.question_status} />
                          <span className="text-muted">Version {it.pinned_version_no}</span>
                        </div>
                        {stale ? (
                          <div className="mt-2 flex flex-wrap items-center gap-2 rounded-md border border-[#e2c28c] bg-bound-soft px-3 py-1.5 text-sm text-bound">
                            <span className="font-bold">
                              Uses version {it.pinned_version_no}; version {it.latest_version_no} is newer.
                            </span>
                            <button type="button" className="btn btn-sm" disabled={busy} onClick={() => refresh.mutate(it.id)}>
                              Use latest version
                            </button>
                          </div>
                        ) : null}
                      </div>
                      <div className="flex flex-none flex-col gap-1 sm:flex-row sm:items-start">
                        <button
                          id={`mv-up-${it.id}`}
                          type="button"
                          className="btn btn-sm"
                          disabled={i === 0 || busy}
                          onClick={() => move(i, -1)}
                          aria-label={`Move question ${i + 1} up`}
                        >
                          ↑<span className="sr-only sm:not-sr-only">Up</span>
                        </button>
                        <button
                          id={`mv-down-${it.id}`}
                          type="button"
                          className="btn btn-sm"
                          disabled={i === items.length - 1 || busy}
                          onClick={() => move(i, 1)}
                          aria-label={`Move question ${i + 1} down`}
                        >
                          ↓<span className="sr-only sm:not-sr-only">Down</span>
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm btn-danger"
                          disabled={busy}
                          onClick={() => remove.mutate(it.id)}
                          aria-label={`Remove question ${i + 1}`}
                        >
                          Remove
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ol>
            )}
          </Section>

          <AddPanel
            a={a}
            onAdded={(out) => {
              setAddResult(out);
              void queryClient.invalidateQueries({ queryKey: key });
              void queryClient.invalidateQueries({ queryKey: ["assessments"] });
              void queryClient.invalidateQueries({ queryKey: ["question"] });
            }}
          />
        </div>

        <aside className="min-w-0 space-y-5">
          <Summary a={a} />
          <Section title="Delete" id="del-h">
            <p className="mb-2 text-sm text-muted">Removes the assessment. The questions stay in the bank.</p>
            <button
              type="button"
              className="btn btn-sm btn-danger"
              disabled={del.isPending}
              onClick={() => {
                if (window.confirm(`Delete “${a.title}”? The questions stay in the bank.`)) del.mutate();
              }}
            >
              Delete assessment
            </button>
            <ErrorNotice error={del.error} />
          </Section>
        </aside>
      </div>
    </>
  );
}

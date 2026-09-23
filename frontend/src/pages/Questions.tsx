import { useMutation } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";
import { api, unwrap } from "../api/client";
import { queryClient, useCourses, useFamilies, useQuestions, useStandards, type QuestionFilter } from "../api/queries";
import { STATUSES, STATUS_LABEL, type QuestionType, type Status } from "../api/types";
import { AddToAssessment, SkippedList } from "../components/AddToAssessment";
import { CodeTag, DokBadge, Empty, ErrorNotice, Loading, Notice, PageHeader, StatusBadge, TypeBadge } from "../components/ui";
import { useDebounced } from "../lib/hooks";
import { pluralize } from "../lib/format";

const PAGE_SIZE = 25;

function isStatus(v: string | null): v is Status {
  return v !== null && (STATUSES as string[]).includes(v);
}

export default function QuestionsPage() {
  const [params, setParams] = useSearchParams();
  const courses = useCourses();
  const families = useFamilies();

  const statusParam = params.get("status");
  const status = isStatus(statusParam) ? statusParam : null;
  const courseId = Number(params.get("course")) || null;
  const standardId = Number(params.get("standard")) || null;
  const familyKey = params.get("family") || null;
  const dok = Number(params.get("dok")) || null;
  const typeParam = params.get("type");
  const qtype: QuestionType | null =
    typeParam === "multiple_choice" || typeParam === "constructed_response" ? typeParam : null;
  const page = Math.max(1, Number(params.get("page")) || 1);
  const [search, setSearch] = useState(params.get("q") ?? "");
  const q = useDebounced(search.trim());

  const update = (patch: Record<string, string | number | null>, resetPage = true) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v === null || v === "") next.delete(k);
      else next.set(k, String(v));
    }
    if (resetPage && !("page" in patch)) next.delete("page");
    setParams(next, { replace: !("page" in patch) });
  };

  useEffect(() => {
    if ((params.get("q") ?? "") === q) return;
    const next = new URLSearchParams(params);
    if (q) next.set("q", q);
    else next.delete("q");
    next.delete("page");
    setParams(next, { replace: true });
  }, [q, params, setParams]);

  const filter: QuestionFilter = {
    status: status ? [status] : [],
    course_id: courseId,
    standard_id: standardId,
    family_key: familyKey,
    dok: dok ? [dok] : [],
    question_type: qtype,
    q: q || null,
    page,
    page_size: PAGE_SIZE,
  };
  const questions = useQuestions(filter);
  const standards = useStandards({ course_id: courseId }, courseId !== null);

  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkTo, setBulkTo] = useState<Status | "">("");
  const [bulkNote, setBulkNote] = useState("");

  const items = questions.data?.items ?? [];
  const counts = questions.data?.status_counts ?? {};
  const allCount = STATUSES.reduce((n, s) => n + (counts[s] ?? 0), 0);
  const total = questions.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pageIds = items.map((i) => i.id);
  const allOnPage = pageIds.length > 0 && pageIds.every((id) => selected.has(id));

  const bulk = useMutation({
    mutationFn: (to: Status) =>
      unwrap(
        api.POST("/api/questions/bulk-status", {
          body: { question_ids: [...selected], to_status: to, note: bulkNote.trim() || null },
        }),
      ),
    onSuccess: (out) => {
      setBulkNote("");
      setSelected(new Set([...Object.keys(out.skipped).map(Number)]));
      void queryClient.invalidateQueries({ queryKey: ["questions"] });
      void queryClient.invalidateQueries({ queryKey: ["question"] });
    },
  });

  const toggleOne = (id: number, on: boolean) => {
    const next = new Set(selected);
    if (on) next.add(id);
    else next.delete(id);
    setSelected(next);
  };
  const toggleAll = (on: boolean) => {
    const next = new Set(selected);
    for (const id of pageIds) {
      if (on) next.add(id);
      else next.delete(id);
    }
    setSelected(next);
  };

  const submitBulk = (e: FormEvent) => {
    e.preventDefault();
    if (bulkTo && selected.size) bulk.mutate(bulkTo);
  };

  const tabs: { key: Status | null; label: string; count: number }[] = [
    { key: null, label: "All", count: allCount },
    ...STATUSES.map((s) => ({ key: s, label: STATUS_LABEL[s], count: counts[s] ?? 0 })),
  ];

  return (
    <>
      <PageHeader
        title="Question bank"
        lead="Review generated questions, approve the ones you’d use, and collect them into assessments."
        actions={
          <Link to="/generate" className="btn btn-primary">
            Generate questions
          </Link>
        }
      />

      <nav aria-label="Filter by status" className="mb-4 overflow-x-auto">
        <ul className="flex min-w-max gap-1 border-b border-line">
          {tabs.map((t) => {
            const active = t.key === status;
            return (
              <li key={t.label}>
                <button
                  type="button"
                  aria-current={active ? "page" : undefined}
                  onClick={() => update({ status: t.key })}
                  className={`-mb-px rounded-t-md border px-3 py-2 font-bold ${
                    active ? "border-line border-b-surface bg-surface text-ink" : "border-transparent text-muted hover:text-ink"
                  }`}
                >
                  {t.label} <span className="tabular-nums font-normal">({t.count})</span>
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      <form
        role="search"
        aria-label="Filter questions"
        className="panel mb-4 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-6"
        onSubmit={(e) => e.preventDefault()}
      >
        <div className="lg:col-span-2">
          <label htmlFor="qb-q" className="field-label">
            Search
          </label>
          <input
            id="qb-q"
            type="search"
            className="input"
            placeholder="Words in the question"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="qb-course" className="field-label">
            Course
          </label>
          <select
            id="qb-course"
            className="input"
            value={courseId ?? ""}
            onChange={(e) => update({ course: e.target.value || null, standard: null })}
          >
            <option value="">All courses</option>
            {courses.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="qb-std" className="field-label">
            Standard
          </label>
          <select
            id="qb-std"
            className="input"
            value={standardId ?? ""}
            disabled={courseId === null}
            aria-describedby={courseId === null ? "qb-std-hint" : undefined}
            onChange={(e) => update({ standard: e.target.value || null })}
          >
            <option value="">All standards</option>
            {standards.data?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.code}
              </option>
            ))}
          </select>
          {courseId === null ? (
            <p id="qb-std-hint" className="hint mt-0.5">
              Pick a course first
            </p>
          ) : null}
        </div>
        <div>
          <label htmlFor="qb-fam" className="field-label">
            Family
          </label>
          <select id="qb-fam" className="input" value={familyKey ?? ""} onChange={(e) => update({ family: e.target.value || null })}>
            <option value="">All families</option>
            {families.data?.map((f) => (
              <option key={f.key} value={f.key}>
                {f.title}
              </option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label htmlFor="qb-dok" className="field-label">
              DOK
            </label>
            <select id="qb-dok" className="input" value={dok ?? ""} onChange={(e) => update({ dok: e.target.value || null })}>
              <option value="">Any</option>
              {[1, 2, 3, 4].map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="qb-type" className="field-label">
              Type
            </label>
            <select id="qb-type" className="input" value={qtype ?? ""} onChange={(e) => update({ type: e.target.value || null })}>
              <option value="">Any</option>
              <option value="multiple_choice">MC</option>
              <option value="constructed_response">CR</option>
            </select>
          </div>
        </div>
      </form>

      <div aria-live="polite" className="mb-4 empty:hidden">
        <ErrorNotice error={bulk.error} />
        {bulk.data ? (
          <Notice tone={Object.keys(bulk.data.skipped).length ? "warn" : "ok"}>
            <p>
              Updated {pluralize(bulk.data.updated.length, "question")} to {STATUS_LABEL[bulk.variables ?? "generated"]}.
            </p>
            <SkippedList skipped={bulk.data.skipped} />
            {Object.keys(bulk.data.skipped).length ? <p className="mt-1 text-sm">Skipped questions stay selected.</p> : null}
          </Notice>
        ) : null}
      </div>

      {selected.size > 0 ? (
        <section aria-label="Bulk actions" className="panel mb-4 space-y-4 border-petrol p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-bold">{pluralize(selected.size, "question")} selected</p>
            <button type="button" className="btn btn-sm btn-quiet" onClick={() => setSelected(new Set())}>
              Clear selection
            </button>
          </div>
          <form onSubmit={submitBulk} className="flex flex-wrap items-end gap-2">
            <div>
              <label htmlFor="bulk-to" className="field-label">
                Change status to
              </label>
              <select id="bulk-to" className="input" value={bulkTo} onChange={(e) => setBulkTo(e.target.value as Status | "")}>
                <option value="">Choose…</option>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {STATUS_LABEL[s]}
                  </option>
                ))}
              </select>
            </div>
            <div className="min-w-[12rem] flex-1">
              <label htmlFor="bulk-note" className="field-label">
                Note <span className="font-normal text-muted">(optional)</span>
              </label>
              <input id="bulk-note" className="input" value={bulkNote} onChange={(e) => setBulkNote(e.target.value)} />
            </div>
            <button type="submit" className="btn btn-primary" disabled={!bulkTo || bulk.isPending}>
              {bulk.isPending ? "Updating…" : "Update status"}
            </button>
          </form>
          <div className="border-t border-line-soft pt-4">
            <AddToAssessment questionIds={[...selected]} />
          </div>
        </section>
      ) : null}

      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p aria-live="polite" className="text-sm text-muted">
          {questions.data ? `${pluralize(total, "question")} match` : ""}
          {questions.isFetching && questions.data ? ", updating…" : ""}
        </p>
        {items.length ? (
          <label className="flex items-center gap-2 text-sm font-bold">
            <input type="checkbox" className="check" checked={allOnPage} onChange={(e) => toggleAll(e.target.checked)} />
            Select all on this page
          </label>
        ) : null}
      </div>

      <ErrorNotice error={questions.error} />
      {questions.isPending ? (
        <Loading />
      ) : items.length === 0 ? (
        <Empty>
          No questions match. <Link to="/generate">Generate a set</Link> or clear a filter.
        </Empty>
      ) : (
        <ul className="panel divide-y divide-line-soft">
          {items.map((it) => (
            <li key={it.id} className={`flex gap-3 p-3 sm:p-4 ${selected.has(it.id) ? "bg-petrol-soft" : ""}`}>
              <input
                type="checkbox"
                className="check mt-1"
                checked={selected.has(it.id)}
                onChange={(e) => toggleOne(it.id, e.target.checked)}
                aria-label={`Select question ${it.id}`}
              />
              <div className="min-w-0 flex-1">
                <Link to={`/questions/${it.id}`} className="booklet line-clamp-3 text-ink no-underline hover:underline">
                  {it.stem}
                </Link>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                  <CodeTag code={it.standard_code} course={it.course_name} />
                  <DokBadge dok={it.dok} />
                  <TypeBadge type={it.question_type} short />
                  <StatusBadge status={it.status} />
                  <span className="text-muted">
                    Version {it.current_version_no}
                    {it.origin === "teacher_edit" ? ", teacher-edited" : ""}
                  </span>
                  {it.stimulus_title ? (
                    <span className="min-w-0 truncate text-muted" title={it.stimulus_title}>
                      Stimulus: {it.stimulus_title}
                    </span>
                  ) : null}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {pages > 1 ? (
        <nav aria-label="Pages" className="mt-4 flex flex-wrap items-center justify-between gap-2">
          <button type="button" className="btn btn-sm" disabled={page <= 1} onClick={() => update({ page: page - 1 })}>
            Previous page
          </button>
          <span className="text-sm text-muted">
            Page {page} of {pages}
          </span>
          <button type="button" className="btn btn-sm" disabled={page >= pages} onClick={() => update({ page: page + 1 })}>
            Next page
          </button>
        </nav>
      ) : null}
    </>
  );
}

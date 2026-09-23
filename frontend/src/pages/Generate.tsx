import { useMutation } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";
import { api, unwrap } from "../api/client";
import { queryClient, useCourses, useFamilies, useStandard, useStandards } from "../api/queries";
import {
  TYPE_LABEL,
  type GeneratePreview,
  type GenerateRequest,
  type GenerateSaveOut,
  type GeneratedGroup,
  type QuestionType,
} from "../api/types";
import { QuestionBody } from "../components/QuestionBody";
import { Stimulus } from "../components/Stimulus";
import { CodeTag, DokBadge, ErrorNotice, Notice, PageHeader, TypeBadge } from "../components/ui";
import { humanize, pluralize } from "../lib/format";
import { generateUrl } from "../lib/links";

const QTYPES: QuestionType[] = ["multiple_choice", "constructed_response"];

function listParam(v: string | null): string[] {
  return v ? v.split(",").map((x) => x.trim()).filter(Boolean) : [];
}

function sameOptions(a: GenerateRequest, b: GenerateRequest): boolean {
  const norm = (r: GenerateRequest) =>
    JSON.stringify({
      s: r.standard_id,
      f: r.family_key,
      d: [...(r.doks ?? [])].sort(),
      t: [...(r.question_types ?? [])].sort(),
      k: [...(r.template_keys ?? [])].sort(),
      q: r.quantity,
    });
  return norm(a) === norm(b);
}

function GroupView({ group, total, showKey }: { group: GeneratedGroup; total: number; showKey: boolean }) {
  return (
    <section className="panel p-4 sm:p-6" aria-labelledby={`group-${group.index}`}>
      <h3 id={`group-${group.index}`} className="mb-3 text-sm font-bold text-muted">
        Data set {group.index + 1} of {total}. Every data set is generated separately, so its numbers differ from the
        others.
      </h3>
      <div className="rounded-md border border-line-soft bg-[#fbfcfc] p-4">
        <Stimulus body={group.stimulus} />
      </div>
      <ol className="mt-5 space-y-6">
        {group.questions.map((q, i) => (
          <li key={i} className="border-t border-line-soft pt-4">
            <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
              <span className="font-bold">{q.title}</span>
              <DokBadge dok={q.dok} />
              <TypeBadge type={q.question_type} short />
            </div>
            <QuestionBody
              stem={q.stem}
              questionType={q.question_type}
              choices={q.choices}
              answer={q.answer}
              explanation={q.explanation}
              showKey={showKey}
              answerLines={q.question_type === "constructed_response" && !showKey ? 3 : 0}
            />
            <p className="mt-2 text-sm text-muted">
              Targets observable performance ({humanize(q.observable.category)}):{" "}
              <span className="text-ink">{q.observable.text ?? `item ${q.observable.index + 1}`}</span>
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}

export default function GeneratePage() {
  const [params, setParams] = useSearchParams();
  const courses = useCourses();
  const families = useFamilies();

  const [chosenCourseId, setCourseId] = useState<number | null>(Number(params.get("course")) || null);
  const [standardId, setStandardId] = useState<number | null>(Number(params.get("standard")) || null);
  const [chosenFamilyKey, setFamilyKey] = useState<string>(params.get("family") ?? "");
  const [doks, setDoks] = useState<number[]>(
    listParam(params.get("doks")).map(Number).filter((n) => n >= 1 && n <= 4),
  );
  const [types, setTypes] = useState<QuestionType[]>(
    listParam(params.get("types")).filter((t): t is QuestionType => (QTYPES as string[]).includes(t)),
  );
  const [templates, setTemplates] = useState<string[]>(listParam(params.get("templates")));
  const [quantity, setQuantity] = useState<string>(params.get("quantity") ?? "5");
  const [seed, setSeed] = useState<string>(params.get("seed") ?? "");
  const [showKey, setShowKey] = useState(true);
  const [generationMode, setGenerationMode] = useState<"classroom" | "eocep">("classroom");
  const [preview, setPreview] = useState<{ request: GenerateRequest; result: GeneratePreview } | null>(null);
  const [saved, setSaved] = useState<GenerateSaveOut | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  // A deep link may carry only a standard id; its course comes from the standard.
  const prefillStandard = useStandard(chosenCourseId === null ? standardId : null);
  const courseId =
    chosenCourseId ??
    prefillStandard.data?.course_id ??
    (standardId === null ? (courses.data?.[0]?.id ?? null) : null);

  const standards = useStandards({ course_id: courseId, with_family_only: true }, courseId !== null);
  const familyOptions = useMemo(
    () => (families.data ?? []).filter((f) => standardId !== null && f.bindings.some((b) => b.standard_ids.includes(standardId))),
    [families.data, standardId],
  );
  // With a single bound family, it is selected without an extra click.
  const family =
    familyOptions.find((f) => f.key === chosenFamilyKey) ?? (familyOptions.length === 1 ? familyOptions[0] : null);
  const familyKey = family?.key ?? "";

  const qty = Math.round(Number(quantity));
  const qtyValid = Number.isFinite(qty) && qty >= 1 && qty <= 40;
  const ready = standardId !== null && family !== null && qtyValid;

  const buildRequest = (seedValue: string | null): GenerateRequest => ({
    standard_id: standardId ?? 0,
    family_key: familyKey,
    doks: [...doks].sort(),
    question_types: types,
    template_keys: templates.filter((k) => family?.templates.some((t) => t.key === k)),
    quantity: qty,
    seed: seedValue && seedValue.trim() ? seedValue.trim() : null,
    generation_mode: generationMode,
  });

  const runPreview = useMutation({
    mutationFn: (req: GenerateRequest) => unwrap(api.POST("/api/generate/preview", { body: req })),
    onSuccess: (result, req) => {
      setPreview({ request: req, result });
      setSaved(null);
      setSeed(result.seed);
      setParams(
        new URLSearchParams(
          generateUrl({ ...req, course_id: courseId, seed: result.seed }).split("?")[1],
        ),
        { replace: true },
      );
      requestAnimationFrame(() => resultsRef.current?.focus());
    },
  });

  const save = useMutation({
    mutationFn: (req: GenerateRequest) => unwrap(api.POST("/api/generate/save", { body: req })),
    onSuccess: (out) => {
      setSaved(out);
      void queryClient.invalidateQueries({ queryKey: ["questions"] });
      void queryClient.invalidateQueries({ queryKey: ["standard"] });
    },
  });

  // "Regenerate this set" links carry preview=1 to show the set straight away.
  const autoRan = useRef(false);
  useEffect(() => {
    if (!autoRan.current && params.get("preview") === "1" && ready) {
      autoRan.current = true;
      runPreview.mutate(buildRequest(seed));
    }
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (ready) runPreview.mutate(buildRequest(seed));
  };

  const toggle = <T,>(list: T[], v: T, on: boolean) => (on ? [...list, v] : list.filter((x) => x !== v));
  const stale = preview !== null && !sameOptions(preview.request, buildRequest(null));
  const totalQuestions = preview?.result.groups.reduce((n, g) => n + g.questions.length, 0) ?? 0;

  return (
    <>
      <PageHeader
        title="Generate questions"
        lead="Pick a standard and a question family. The family builds a data set from a seed and writes questions from it; the same seed always reproduces the same set."
      />

      <form onSubmit={submit} className="grid gap-5 lg:grid-cols-2" aria-label="Generation options">
        <fieldset className="panel p-4 sm:p-5">
          <legend className="sr-only">Step 1: Course and standard</legend>
          <h2 className="mb-3 text-lg font-bold">
            <span className="mr-2 text-muted">1.</span>Course and standard
          </h2>
          <label htmlFor="g-mode" className="field-label">Generation mode</label>
          <select id="g-mode" className="input mb-4" value={generationMode} onChange={(e) => setGenerationMode(e.target.value as "classroom" | "eocep")}>
            <option value="classroom">Classroom</option>
            <option value="eocep">EOCEP practice (Biology 1)</option>
          </select>
          <label htmlFor="g-course" className="field-label">
            Course
          </label>
          <select
            id="g-course"
            className="input mb-4"
            value={courseId ?? ""}
            onChange={(e) => {
              setCourseId(Number(e.target.value) || null);
              setStandardId(null);
              setFamilyKey("");
              setTemplates([]);
            }}
          >
            {courses.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.use_year})
              </option>
            ))}
          </select>
          <p id="g-std-hint" className="field-label">
            Standard <span className="font-normal text-muted">(only standards with a question family)</span>
          </p>
          {standards.data?.length === 0 ? (
            <p className="text-muted">No question families are written for this course yet.</p>
          ) : (
            <div role="radiogroup" aria-labelledby="g-std-hint" className="space-y-2">
              {standards.data?.map((s) => (
                <label
                  key={s.id}
                  className={`flex cursor-pointer gap-3 rounded-md border p-3 ${
                    s.id === standardId ? "border-petrol bg-petrol-soft" : "border-line"
                  }`}
                >
                  <input
                    type="radio"
                    name="standard"
                    className="check mt-1"
                    checked={s.id === standardId}
                    onChange={() => {
                      setStandardId(s.id);
                      setFamilyKey("");
                      setTemplates([]);
                    }}
                  />
                  <span className="min-w-0">
                    <CodeTag code={s.code} course={s.course_name} />
                    <span className="mt-1 block text-[0.9375rem]">{s.performance_expectation}</span>
                  </span>
                </label>
              ))}
            </div>
          )}
          <ErrorNotice error={standards.error} />
        </fieldset>

        <fieldset className="panel p-4 sm:p-5" disabled={standardId === null}>
          <legend className="sr-only">Step 2: Question family</legend>
          <h2 className="mb-3 text-lg font-bold">
            <span className="mr-2 text-muted">2.</span>Question family
          </h2>
          {standardId === null ? (
            <p className="text-muted">Choose a standard first.</p>
          ) : familyOptions.length === 0 ? (
            <p className="text-muted">No family is bound to this standard.</p>
          ) : (
            <div className="space-y-2">
              {familyOptions.map((f) => (
                <label
                  key={f.key}
                  className={`flex cursor-pointer gap-3 rounded-md border p-3 ${
                    f.key === familyKey ? "border-petrol bg-petrol-soft" : "border-line"
                  }`}
                >
                  <input
                    type="radio"
                    name="family"
                    className="check mt-1"
                    checked={f.key === familyKey}
                    onChange={() => {
                      setFamilyKey(f.key);
                      setTemplates([]);
                    }}
                  />
                  <span className="min-w-0">
                    <span className="block font-bold">{f.title}</span>
                    <span className="block text-sm text-muted">
                      Version {f.version}, {pluralize(f.templates.length, "template")}
                    </span>
                    <span className="mt-1 block text-[0.9375rem]">{f.description}</span>
                  </span>
                </label>
              ))}
            </div>
          )}
        </fieldset>

        <fieldset className="panel p-4 sm:p-5 lg:col-span-2" disabled={!family}>
          <legend className="sr-only">Step 3: Options</legend>
          <h2 className="mb-3 text-lg font-bold">
            <span className="mr-2 text-muted">3.</span>Options
          </h2>
          <div className="grid gap-5 md:grid-cols-[auto_auto_1fr]">
            <fieldset>
              <legend className="field-label">Depth of Knowledge</legend>
              <div className="flex flex-wrap gap-3">
                {[1, 2, 3, 4].map((d) => {
                  const available = family?.templates.some((t) => t.dok === d) ?? true;
                  return (
                    <label key={d} className={`flex items-center gap-1.5 ${available ? "" : "text-muted"}`}>
                      <input
                        type="checkbox"
                        className="check"
                        checked={doks.includes(d)}
                        disabled={!available}
                        onChange={(e) => setDoks(toggle(doks, d, e.target.checked))}
                      />
                      DOK {d}
                    </label>
                  );
                })}
              </div>
              <p className="hint mt-1">None checked means any level.</p>
            </fieldset>
            <fieldset>
              <legend className="field-label">Question type</legend>
              <div className="flex flex-wrap gap-3">
                {QTYPES.map((t) => (
                  <label key={t} className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      className="check"
                      checked={types.includes(t)}
                      onChange={(e) => setTypes(toggle(types, t, e.target.checked))}
                    />
                    {TYPE_LABEL[t]}
                  </label>
                ))}
              </div>
              <p className="hint mt-1">None checked means both.</p>
            </fieldset>
            <div className="grid grid-cols-2 gap-3 sm:max-w-sm">
              <div>
                <label htmlFor="g-qty" className="field-label">
                  Quantity
                </label>
                <input
                  id="g-qty"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={40}
                  className="input"
                  value={quantity}
                  aria-invalid={!qtyValid}
                  aria-describedby="g-qty-hint"
                  onChange={(e) => setQuantity(e.target.value)}
                />
                <p id="g-qty-hint" className={`hint mt-1 ${qtyValid ? "" : "font-bold text-danger"}`}>
                  1 to 40 questions
                </p>
              </div>
              <div>
                <label htmlFor="g-seed" className="field-label">
                  Seed
                </label>
                <input
                  id="g-seed"
                  className="input"
                  value={seed}
                  placeholder="Random"
                  aria-describedby="g-seed-hint"
                  onChange={(e) => setSeed(e.target.value)}
                />
                <p id="g-seed-hint" className="hint mt-1">
                  Optional
                </p>
              </div>
            </div>
          </div>

          {family ? (
            <details className="mt-5 rounded-md border border-line" open={templates.length > 0}>
              <summary className="cursor-pointer px-3 py-2 font-bold">
                Templates{" "}
                <span className="font-normal text-muted">
                  ({templates.length ? `${templates.length} selected` : "all that match DOK and type"})
                </span>
              </summary>
              <ul className="divide-y divide-line-soft border-t border-line">
                {family.templates.map((t) => (
                  <li key={t.key}>
                    <label className="flex cursor-pointer gap-3 px-3 py-2.5">
                      <input
                        type="checkbox"
                        className="check mt-1"
                        checked={templates.includes(t.key)}
                        onChange={(e) => setTemplates(toggle(templates, t.key, e.target.checked))}
                      />
                      <span className="min-w-0">
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="font-bold">{t.title}</span>
                          <DokBadge dok={t.dok} />
                          <TypeBadge type={t.question_type} short />
                        </span>
                        <span className="mt-0.5 block text-sm text-muted">
                          Cites {humanize(t.observable_category)}: {t.observable_text ?? `item ${t.observable_index + 1}`}
                        </span>
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button type="submit" className="btn btn-primary" disabled={!ready || runPreview.isPending}>
              {runPreview.isPending ? "Generating preview…" : "Preview"}
            </button>
            {!ready && standardId !== null && family === null ? (
              <span className="text-sm text-muted">Choose a family to continue.</span>
            ) : null}
          </div>
        </fieldset>
      </form>

      <div aria-live="polite" className="mt-5">
        <ErrorNotice error={runPreview.error} title="The preview could not be generated." />
      </div>

      {preview ? (
        <div ref={resultsRef} tabIndex={-1} className="mt-8 outline-none" aria-labelledby="preview-h">
          <div className="panel z-10 mb-5 p-4 lg:sticky lg:top-2">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 id="preview-h" className="text-xl font-bold">
                  Preview: {pluralize(totalQuestions, "question")} in{" "}
                  {pluralize(preview.result.groups.length, "data set")}
                </h2>
                <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                  <CodeTag code={preview.result.standard.code} course={preview.result.standard.course_name} />
                  <span>
                    {family?.title ?? preview.result.family_key}, version {preview.result.family_version}
                  </span>
                  <span>
                    Seed <code className="rounded bg-paper px-1.5 py-0.5 font-bold">{preview.result.seed}</code>
                  </span>
                </p>
                {stale ? (
                  <p className="mt-1 text-sm font-bold text-bound">
                    Options have changed since this preview. Saving keeps the previewed set; preview again to apply them.
                  </p>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="btn btn-sm"
                  aria-pressed={showKey}
                  onClick={() => setShowKey((v) => !v)}
                >
                  {showKey ? "Hide answer key" : "Show answer key"}
                </button>
                <button
                  type="button"
                  className="btn btn-sm"
                  disabled={runPreview.isPending}
                  onClick={() => runPreview.mutate({ ...preview.request, seed: null })}
                >
                  New variation
                </button>
                <button
                  type="button"
                  className="btn btn-sm"
                  disabled={runPreview.isPending}
                  onClick={() => runPreview.mutate({ ...preview.request, seed: preview.result.seed })}
                >
                  Same seed
                </button>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  disabled={save.isPending || saved !== null}
                  onClick={() => save.mutate({ ...preview.request, seed: preview.result.seed })}
                >
                  {save.isPending ? "Saving…" : saved ? "Saved" : "Save to question bank"}
                </button>
              </div>
            </div>
            <div aria-live="polite">
              <ErrorNotice error={save.error} title="The set was not saved." />
              {saved ? (
                <div className="mt-3">
                  <Notice>
                    <p className="font-bold">
                      Saved {pluralize(saved.question_ids.length, "question")} to the bank as generated (run{" "}
                      {saved.run_id}, seed {saved.seed}).
                    </p>
                    <p className="mt-1">
                      <Link
                        to={`/questions?status=generated&course=${preview.result.standard.course_id}&standard=${preview.result.standard.id}&family=${preview.result.family_key}`}
                        className="font-bold"
                      >
                        Review them in the question bank
                      </Link>{" "}
                      or open one:{" "}
                      {saved.question_ids.map((id, i) => (
                        <span key={id}>
                          {i ? ", " : ""}
                          <Link to={`/questions/${id}`}>#{id}</Link>
                        </span>
                      ))}
                    </p>
                  </Notice>
                </div>
              ) : null}
            </div>
          </div>

          <div className="space-y-6">
            {preview.result.groups.map((g) => (
              <GroupView key={`${preview.result.seed}-${g.index}`} group={g} total={preview.result.groups.length} showKey={showKey} />
            ))}
          </div>
        </div>
      ) : null}
    </>
  );
}

import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";
import { api, unwrap } from "../api/client";
import { queryClient, useFamilies } from "../api/queries";
import type { BundleGeneratePreview, BundleGenerateRequest, GenerateSaveOut, QuestionType } from "../api/types";
import { QuestionBody } from "../components/QuestionBody";
import { Stimulus } from "../components/Stimulus";
import { CodeTag, DokBadge, ErrorNotice, Notice, PageHeader, TypeBadge } from "../components/ui";
import { humanize, pluralize } from "../lib/format";

export default function BundleGeneratePage() {
  const [params] = useSearchParams();
  const bundleId = Number(params.get("bundle")) || 0;
  const familyKey = params.get("family") ?? "";
  const families = useFamilies();
  const bundles = useQuery({
    queryKey: ["bundles", "all"],
    queryFn: () => unwrap(api.GET("/api/bundles")),
    staleTime: 5 * 60_000,
  });
  const family = families.data?.find((item) => item.key === familyKey) ?? null;
  const bundle = bundles.data?.find((item) => item.id === bundleId) ?? null;
  const supported = useMemo(() => {
    const available = new Set(bundle?.aligned.filter((item) => !item.partial).map((item) => item.code));
    return family !== null && family.bindings.every((binding) => available.has(binding.code));
  }, [bundle, family]);

  const [quantity, setQuantity] = useState("5");
  const [seed, setSeed] = useState("");
  const [templates, setTemplates] = useState<string[]>([]);
  const [showKey, setShowKey] = useState(true);
  const [preview, setPreview] = useState<{ request: BundleGenerateRequest; result: BundleGeneratePreview } | null>(null);
  const [saved, setSaved] = useState<GenerateSaveOut | null>(null);
  const qty = Math.round(Number(quantity));
  const qtyValid = Number.isFinite(qty) && qty >= 1 && qty <= 40;

  const request = (seedValue: string | null): BundleGenerateRequest => ({
    bundle_id: bundleId,
    family_key: familyKey,
    quantity: qty,
    seed: seedValue?.trim() || null,
    template_keys: templates,
    doks: [],
    question_types: [],
  });
  const runPreview = useMutation({
    mutationFn: (body: BundleGenerateRequest) => unwrap(api.POST("/api/generate/bundle/preview", { body })),
    onSuccess: (result, body) => {
      setPreview({ request: body, result });
      setSeed(result.seed);
      setSaved(null);
    },
  });
  const save = useMutation({
    mutationFn: (body: BundleGenerateRequest) => unwrap(api.POST("/api/generate/bundle/save", { body })),
    onSuccess: (result) => {
      setSaved(result);
      void queryClient.invalidateQueries({ queryKey: ["questions"] });
    },
  });
  const toggleTemplate = (key: string, checked: boolean) =>
    setTemplates((current) => (checked ? [...current, key] : current.filter((item) => item !== key)));
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (supported && qtyValid) runPreview.mutate(request(seed));
  };
  const standards = new Map(preview?.result.standards.map((standard) => [standard.code, standard]));

  return (
    <>
      <PageHeader
        title="Generate shared stimulus"
        lead="One deterministic investigation can support questions aligned to more than one performance expectation."
        actions={<Link className="btn" to="/bundles">Back to bundles</Link>}
      />
      {!bundleId || !familyKey ? <ErrorNotice error="Choose a supported shared generator from the Bundles page." /> : null}
      {bundle ? <div className="panel mb-5 p-4"><p className="font-bold">{bundle.name}</p><p className="mt-1 text-sm text-muted">{bundle.narrative}</p></div> : null}
      {family && bundle ? (
        <form className="panel p-4 sm:p-5" onSubmit={submit}>
          <h2 className="text-lg font-bold">{family.title}</h2>
          <p className="mt-1 text-muted">{family.description}</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label><span className="field-label">Quantity</span><input className="input" min={1} max={40} type="number" value={quantity} onChange={(event) => setQuantity(event.target.value)} /></label>
            <label><span className="field-label">Seed</span><input className="input" placeholder="Random" value={seed} onChange={(event) => setSeed(event.target.value)} /></label>
          </div>
          <details className="mt-5 rounded-md border border-line" open={templates.length > 0}>
            <summary className="cursor-pointer px-3 py-2 font-bold">Templates <span className="font-normal text-muted">({templates.length || "all"})</span></summary>
            <ul className="divide-y divide-line-soft border-t border-line">
              {family.templates.map((template) => (
                <li key={template.key}><label className="flex cursor-pointer gap-3 px-3 py-2.5"><input className="check mt-1" type="checkbox" checked={templates.includes(template.key)} onChange={(event) => toggleTemplate(template.key, event.target.checked)} /><span><span className="font-bold">{template.title}</span> <DokBadge dok={template.dok} /> <TypeBadge type={template.question_type as QuestionType} short /><span className="mt-1 block text-sm text-muted">{template.standard_code}: {template.observable_text}</span></span></label></li>
              ))}
            </ul>
          </details>
          {!supported ? <Notice tone="warn"><p>This generator is not supported by the selected bundle.</p></Notice> : null}
          <button className="btn btn-primary mt-5" disabled={!supported || !qtyValid || runPreview.isPending} type="submit">{runPreview.isPending ? "Generating preview…" : "Preview"}</button>
        </form>
      ) : null}
      <ErrorNotice error={bundles.error || families.error || runPreview.error} title="The shared stimulus could not be generated." />
      {preview ? (
        <section className="mt-6">
          <div className="panel mb-5 p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-bold">Preview: {pluralize(preview.result.groups.reduce((total, group) => total + group.questions.length, 0), "question")}</h2><p className="text-sm text-muted">Seed <code>{preview.result.seed}</code></p></div><div className="flex gap-2"><button className="btn btn-sm" type="button" onClick={() => setShowKey((value) => !value)}>{showKey ? "Hide answer key" : "Show answer key"}</button><button className="btn btn-primary btn-sm" type="button" disabled={save.isPending || saved !== null} onClick={() => save.mutate({ ...preview.request, seed: preview.result.seed })}>{save.isPending ? "Saving…" : saved ? "Saved" : "Save to question bank"}</button></div></div>{saved ? <Notice><p>Saved {pluralize(saved.question_ids.length, "question")} to the bank.</p></Notice> : null}</div>
          <div className="space-y-6">{preview.result.groups.map((group) => <section key={group.index} className="panel p-4 sm:p-6"><Stimulus body={group.stimulus} /><ol className="mt-5 space-y-6">{group.questions.map((question, index) => { const standard = standards.get(question.standard_code ?? ""); return <li key={index} className="border-t border-line-soft pt-4"><div className="mb-2 flex flex-wrap items-center gap-2"><span className="font-bold">{question.title}</span><DokBadge dok={question.dok} /><TypeBadge type={question.question_type} short />{standard ? <CodeTag code={standard.code} course={standard.course_name} /> : null}</div><QuestionBody stem={question.stem} questionType={question.question_type} choices={question.choices} answer={question.answer} explanation={question.explanation} showKey={showKey} answerLines={question.question_type === "constructed_response" && !showKey ? 3 : 0} /><p className="mt-2 text-sm text-muted">Targets {humanize(question.observable.category)}: {question.observable.text}</p></li>; })}</ol></section>)}</div>
        </section>
      ) : null}
    </>
  );
}

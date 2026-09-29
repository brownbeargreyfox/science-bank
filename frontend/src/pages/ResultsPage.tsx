import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api, cleanQuery, unwrap } from "../api/client";
import { queryClient, useCourses, useFamilies, useStandards } from "../api/queries";
import type { SummaryRow, VariantRecord } from "../api/types";
import { CodeTag, Empty, ErrorNotice, Loading, Notice, PageHeader, Pill, Section } from "../components/ui";
import { formatDate } from "../lib/format";
import { accuracyText } from "../lib/results";

const PAGE = 25;
const MAX_SELECTION = 20;

export default function ResultsPage() {
  const courses = useCourses();
  const families = useFamilies();
  const [courseId, setCourseId] = useState("");
  const [standardId, setStandardId] = useState("");
  const [familyKey, setFamilyKey] = useState("");
  const [offset, setOffset] = useState(0);
  const standards = useStandards({ course_id: courseId ? Number(courseId) : null });
  const summary = useQuery({
    queryKey: ["results", "summary", courseId, standardId, familyKey, offset],
    queryFn: () => unwrap(api.GET("/api/results/summary", { params: { query: cleanQuery({ course_id: courseId ? Number(courseId) : undefined, standard_id: standardId ? Number(standardId) : undefined, family_key: familyKey || undefined, limit: PAGE, offset }) } })),
  });
  const [selected, setSelected] = useState<Map<number, string>>(new Map());
  const [records, setRecords] = useState<VariantRecord[] | null>(null);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [savedIds, setSavedIds] = useState<number[] | null>(null);
  const toggle = (row: SummaryRow) => setSelected((previous) => { const next = new Map(previous); if (next.has(row.question_id)) next.delete(row.question_id); else next.set(row.question_id, row.stem); return next; });
  const preview = useMutation({ mutationFn: () => unwrap(api.POST("/api/questions/variants/preview", { body: { question_ids: [...selected.keys()] } })), onSuccess: (out) => { setRecords(out.records); setPicked(new Set(out.records.filter((record) => record.status === "candidate").map((record) => record.parent_id))); setSavedIds(null); } });
  const save = useMutation({
    mutationFn: () => {
      const tokens = (records ?? []).filter((record) => record.status === "candidate" && picked.has(record.parent_id) && record.candidate_token).map((record) => record.candidate_token!);
      return unwrap(api.POST("/api/questions/variants/save", { body: { tokens } }));
    },
    onSuccess: (out) => { setSavedIds(out.question_ids); setRecords(null); setSelected(new Map()); void queryClient.invalidateQueries({ queryKey: ["questions"] }); void queryClient.invalidateQueries({ queryKey: ["usage"] }); },
  });
  const rows = summary.data?.items ?? [];
  const total = summary.data?.total ?? 0;
  const resetPaging = () => setOffset(0);
  return <>
    <PageHeader title="Results" lead="Questions from your recorded uses, lowest accuracy first. Choose questions to get new generated items from the same family and template." />
    <Notice tone="info">A low percentage does not show why students missed a question. Worth checking: the wording and reading load, the question format, whether the content was taught, and whether the key or a choice is ambiguous.</Notice>
    <div className="my-4 grid gap-3 sm:grid-cols-3">
      <div><label htmlFor="f-course" className="field-label">Course</label><select id="f-course" className="input" value={courseId} onChange={(event) => { setCourseId(event.target.value); setStandardId(""); resetPaging(); }}><option value="">All courses</option>{courses.data?.map((course) => <option key={course.id} value={course.id}>{course.name} ({course.use_year})</option>)}</select></div>
      <div><label htmlFor="f-standard" className="field-label">Standard</label><select id="f-standard" className="input" value={standardId} onChange={(event) => { setStandardId(event.target.value); resetPaging(); }}><option value="">All standards</option>{standards.data?.map((standard) => <option key={standard.id} value={standard.id}>{standard.code}</option>)}</select></div>
      <div><label htmlFor="f-family" className="field-label">Question family</label><select id="f-family" className="input" value={familyKey} onChange={(event) => { setFamilyKey(event.target.value); resetPaging(); }}><option value="">All families</option>{families.data?.map((family) => <option key={family.key} value={family.key}>{family.title}</option>)}</select></div>
    </div>
    <ErrorNotice error={summary.error} />
    {summary.isPending ? <Loading /> : rows.length === 0 ? <Empty>No recorded uses match. Record a use from an assessment page, then enter results.</Empty> : <div className="panel overflow-x-auto"><table className="w-full text-sm"><caption className="sr-only">Questions by accuracy across your recorded uses</caption><thead><tr className="border-b border-line-soft text-left"><th scope="col" className="p-3"><span className="sr-only">Select</span></th><th scope="col" className="p-3">Question</th><th scope="col" className="p-3">Correct / attempted</th><th scope="col" className="p-3">Uses</th><th scope="col" className="p-3">Last used</th></tr></thead><tbody>{rows.map((row) => <tr key={row.question_id} className="border-b border-line-soft align-top"><td className="p-3"><input type="checkbox" className="check" aria-label={`Select question ${row.question_id}`} checked={selected.has(row.question_id)} disabled={!selected.has(row.question_id) && selected.size >= MAX_SELECTION} onChange={() => toggle(row)} /></td><td className="min-w-64 p-3"><Link to={`/questions/${row.question_id}`}>{row.stem.slice(0, 120)}{row.stem.length > 120 ? "…" : ""}</Link><div className="mt-1"><CodeTag code={row.standard_code} course={row.course_name} /></div></td><td className="p-3 tabular-nums"><div className="font-bold">{row.attempted > 0 ? `${row.correct} / ${row.attempted}` : "No data"}</div><div>{accuracyText(row.correct, row.attempted)}</div>{row.limited_responses ? <Pill>Limited response count</Pill> : null}</td><td className="p-3 tabular-nums">{row.times_used}</td><td className="p-3">{row.last_used ? formatDate(row.last_used) : "—"}</td></tr>)}</tbody></table></div>}
    {total > PAGE ? <div className="my-3 flex items-center gap-2"><button type="button" className="btn btn-sm" disabled={offset === 0} onClick={() => setOffset(offset - PAGE)}>Previous</button><span className="text-sm text-muted">{offset + 1}–{Math.min(offset + PAGE, total)} of {total}</span><button type="button" className="btn btn-sm" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>Next</button></div> : null}
    <div className="my-4 flex flex-wrap items-center gap-3" aria-live="polite"><button type="button" className="btn btn-primary" disabled={selected.size === 0 || preview.isPending} onClick={() => preview.mutate()}>{preview.isPending ? "Generating…" : `Make practice variants (${selected.size})`}</button><span className="text-sm text-muted">Up to {MAX_SELECTION} at a time. Nothing is saved until you choose “Save selected variants”.</span><ErrorNotice error={preview.error ?? save.error} /></div>
    {savedIds ? <Notice tone="ok">Saved {savedIds.length} new generated {savedIds.length === 1 ? "item" : "items"}: {savedIds.map((id, index) => <span key={id}>{index ? ", " : ""}<Link to={`/questions/${id}`}>question {id}</Link></span>)}. They are separate questions; results for them are recorded separately from the originals’.</Notice> : null}
    {records ? <Section title="Review new generated items" id="variants-h"><p className="mb-3 text-sm text-muted">Each is a new generated item from the same family and template as its original. It may not be equivalent in difficulty. Tick the ones to keep.</p><ul className="space-y-4">{records.map((record) => <li key={record.parent_id} className="rounded border border-line-soft p-3"><p className="text-sm text-muted">Original (question {record.parent_id}): {selected.get(record.parent_id)}</p>{record.status === "unavailable" || !record.candidate ? <p className="mt-2 text-sm"><strong>No new item available.</strong> {record.reason}</p> : <div className="mt-2"><label className="flex items-start gap-2"><input type="checkbox" className="check mt-1" checked={picked.has(record.parent_id)} onChange={() => setPicked((previous) => { const next = new Set(previous); if (next.has(record.parent_id)) next.delete(record.parent_id); else next.add(record.parent_id); return next; })} /><span><span className="font-bold">{record.candidate.stem}</span>{record.candidate.choices.length ? <ul className="mt-1 space-y-0.5 text-sm">{record.candidate.choices.map((choice) => <li key={String(choice.label)}>{String(choice.label)}. {String(choice.text)}{choice.correct === true ? " ✓" : ""}</li>)}</ul> : <span className="mt-1 block text-sm">{record.candidate.answer}</span>}</span></label></div>}</li>)}</ul><div className="mt-4 flex gap-2"><button type="button" className="btn btn-primary" disabled={picked.size === 0 || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "Saving…" : `Save selected variants (${picked.size})`}</button><button type="button" className="btn" onClick={() => setRecords(null)}>Discard</button></div></Section> : null}
  </>;
}

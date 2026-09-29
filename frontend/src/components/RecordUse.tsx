import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { api, unwrap } from "../api/client";
import { queryClient } from "../api/queries";
import type { AssessmentDetail } from "../api/types";
import { formatDate } from "../lib/format";
import { ErrorNotice, Section } from "./ui";

function todayLocal(): string {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export default function RecordUse({ a }: { a: AssessmentDetail }) {
  const navigate = useNavigate();
  const [label, setLabel] = useState("");
  const [date, setDate] = useState(todayLocal());
  const [sections, setSections] = useState("");
  const names = sections.split(",").map((section) => section.trim()).filter(Boolean);
  const past = useQuery({
    queryKey: ["administrations", a.id],
    queryFn: () => unwrap(api.GET("/api/assessments/{assessment_id}/administrations", { params: { path: { assessment_id: a.id } } })),
  });
  const create = useMutation({
    mutationFn: () => unwrap(api.POST("/api/assessments/{assessment_id}/administrations", {
      params: { path: { assessment_id: a.id } }, body: { label: label.trim(), administered_on: date, sections: names },
    })),
    onSuccess: (administration) => {
      void queryClient.invalidateQueries({ queryKey: ["administrations", a.id] });
      navigate(`/administrations/${administration.id}`);
    },
  });
  const empty = a.items.length === 0;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!empty && label.trim() && names.length) create.mutate();
  };
  return <Section title="Record use" id="use-h">
    <p className="mb-2 text-sm text-muted">Record that you gave this assessment, then enter how each section did on each question. Your entries are visible to you and to department moderators.</p>
    {empty ? <p className="text-sm text-muted">Add questions to this assessment first.</p> : null}
    <form onSubmit={submit} className="space-y-3">
      <div><label htmlFor="ru-label" className="field-label">Label</label><input id="ru-label" className="input" value={label} placeholder="Unit 3 quiz" disabled={empty} onChange={(event) => setLabel(event.target.value)} /></div>
      <div><label htmlFor="ru-date" className="field-label">Date given</label><input id="ru-date" type="date" className="input" value={date} required disabled={empty} onChange={(event) => setDate(event.target.value)} /></div>
      <div><label htmlFor="ru-sections" className="field-label">Sections <span className="font-normal text-muted">(comma-separated)</span></label><input id="ru-sections" className="input" value={sections} placeholder="Period 2, Period 4" disabled={empty} onChange={(event) => setSections(event.target.value)} /></div>
      <div aria-live="polite"><ErrorNotice error={create.error} /></div>
      <button type="submit" className="btn btn-primary" disabled={empty || !label.trim() || names.length === 0 || create.isPending}>{create.isPending ? "Recording…" : "Record use"}</button>
    </form>
    {past.data && past.data.length > 0 ? <div className="mt-4"><h3 className="mb-1 font-bold">Past uses</h3><ul className="space-y-1 text-sm">{past.data.map((use) => <li key={use.id}><Link to={`/administrations/${use.id}`}>{use.label}</Link>{" "}<span className="text-muted">{formatDate(use.administered_on)}, {use.items_with_data} of {use.item_count} questions have data</span></li>)}</ul></div> : null}
  </Section>;
}

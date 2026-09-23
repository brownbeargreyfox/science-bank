import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";
import { api, unwrap } from "../api/client";
import { queryClient, useAssessments } from "../api/queries";
import { STATUS_LABEL, TYPE_LABEL, type QuestionDetail, type Status } from "../api/types";
import { EditQuestionForm } from "../components/EditQuestionForm";
import { QuestionBody } from "../components/QuestionBody";
import { Stimulus } from "../components/Stimulus";
import {
  CodeTag,
  DokBadge,
  ErrorNotice,
  Hash,
  Loading,
  Meta,
  Notice,
  OriginBadge,
  PageHeader,
  Section,
  StatusBadge,
  TypeBadge,
} from "../components/ui";
import { formatDate, formatDateTime, humanize, parseProvenance } from "../lib/format";
import { generateUrl } from "../lib/links";

function StatusPanel({ q, onChanged }: { q: QuestionDetail; onChanged: (q: QuestionDetail) => void }) {
  const [note, setNote] = useState("");
  const change = useMutation({
    mutationFn: (to: Status) =>
      unwrap(
        api.POST("/api/questions/{question_id}/status", {
          params: { path: { question_id: q.id } },
          body: { to_status: to, note: note.trim() || null },
        }),
      ),
    onSuccess: (updated) => {
      setNote("");
      onChanged(updated);
    },
  });

  return (
    <Section title="Status" id="status-h">
      <p className="mb-3 flex items-center gap-2">
        Currently <StatusBadge status={q.status} />
      </p>
      {q.allowed_transitions.length ? (
        <form onSubmit={(e: FormEvent) => e.preventDefault()} className="space-y-3">
          <div>
            <label htmlFor="st-note" className="field-label">
              Note <span className="font-normal text-muted">(optional)</span>
            </label>
            <input id="st-note" className="input" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
          <div className="flex flex-wrap gap-2">
            {q.allowed_transitions.map((t) => (
              <button
                key={t}
                type="button"
                className={`btn btn-sm ${t === "approved" ? "btn-primary" : t === "rejected" ? "btn-danger" : ""}`}
                disabled={change.isPending}
                onClick={() => change.mutate(t)}
              >
                Mark {STATUS_LABEL[t].toLowerCase()}
              </button>
            ))}
          </div>
        </form>
      ) : (
        <p className="text-muted">No status changes are available from here.</p>
      )}
      <div aria-live="polite" className="mt-2">
        <ErrorNotice error={change.error} />
      </div>
      <h3 className="mt-4 mb-1 font-bold">History</h3>
      <ol className="space-y-2 text-sm">
        {[...q.status_events].reverse().map((ev) => (
          <li key={ev.id} className="border-l-2 border-line pl-3">
            <span className="font-bold">
              {ev.from_status ? `${humanize(ev.from_status)} to ${humanize(ev.to_status)}` : `Created as ${ev.to_status}`}
            </span>
            <span className="block text-muted">{formatDateTime(ev.created_at)}</span>
            {ev.note ? <span className="block">“{ev.note}”</span> : null}
          </li>
        ))}
      </ol>
    </Section>
  );
}

function ProvenancePanel({ q }: { q: QuestionDetail }) {
  const p = parseProvenance(q.provenance);
  const regen =
    p.seed && (p.family?.key ?? q.family_key)
      ? generateUrl({
          course_id: q.standard.course_id,
          standard_id: q.standard.id,
          family_key: p.family?.key ?? q.family_key ?? "",
          seed: p.seed,
          doks: p.options?.doks,
          question_types: p.options?.question_types,
          template_keys: p.options?.template_keys,
          quantity: p.options?.quantity,
          preview: true,
        })
      : null;
  const src = p.source_document;
  return (
    <Section
      title="Provenance"
      id="prov-h"
      actions={
        regen ? (
          <Link to={regen} className="btn btn-sm">
            Regenerate this set
          </Link>
        ) : null
      }
    >
      <p className="mb-2 text-sm text-muted">Recorded when this question was generated.</p>
      <dl>
        <Meta label="Standard">
          <CodeTag code={p.standard?.code ?? q.standard.code} course={p.standard?.course ?? q.standard.course_name} to={`/standards/${q.standard.id}`} />
          <span className="mt-1 block text-sm">{p.standard?.performance_expectation ?? q.standard.performance_expectation}</span>
        </Meta>
        <Meta label="Use year">{p.standard?.use_year ?? q.standard.use_year}</Meta>
        <Meta label="Source document">
          {src?.title ?? "Not recorded"}
          {src?.published ? <span className="block text-sm text-muted">Published {formatDate(src.published)}</span> : null}
          {src?.authority ? <span className="block text-sm text-muted">{src.authority}</span> : null}
          {src?.url ? (
            <a href={src.url} target="_blank" rel="noreferrer" className="block text-sm break-all">
              SCDE standards page
            </a>
          ) : null}
        </Meta>
        {src?.data_file ? (
          <Meta label="Data file">
            <code className="text-sm break-all">{src.data_file}</code>
            <Hash value={src.content_sha256} />
          </Meta>
        ) : null}
        <Meta label="Family">
          {p.family?.title ?? q.family_key ?? "Not recorded"}
          {p.family?.version ? <span className="block text-sm text-muted">Version {p.family.version}</span> : null}
        </Meta>
        <Meta label="Template">
          {p.template?.title ?? q.template_key ?? "Not recorded"}
          {p.template?.key ? <code className="block text-sm text-muted">{p.template.key}</code> : null}
        </Meta>
        <Meta label="Observable performance">
          {p.observable_performance?.text ?? "Not recorded"}
          {p.observable_performance?.category ? (
            <span className="block text-sm text-muted">{humanize(p.observable_performance.category)}</span>
          ) : null}
        </Meta>
        <Meta label="Seed">
          <code className="font-bold break-all">{p.seed ?? "Not recorded"}</code>
        </Meta>
        <Meta label="Data set">
          {p.group_index !== undefined ? `Group ${p.group_index + 1}` : "Not recorded"}
          {p.attempt ? <span className="text-sm text-muted">, attempt {p.attempt}</span> : null}
        </Meta>
        <Meta label="Generated">{formatDateTime(p.generated_at) || "Not recorded"}</Meta>
      </dl>
    </Section>
  );
}

export default function QuestionDetailPage() {
  const id = Number(useParams().id);
  const q = useQuery({
    queryKey: ["question", id],
    queryFn: () => unwrap(api.GET("/api/questions/{question_id}", { params: { path: { question_id: id } } })),
    enabled: Number.isFinite(id),
  });
  const assessments = useAssessments();
  const [viewNo, setViewNo] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const applyUpdate = (updated: QuestionDetail, msg: string) => {
    queryClient.setQueryData(["question", id], updated);
    void queryClient.invalidateQueries({ queryKey: ["questions"] });
    void queryClient.invalidateQueries({ queryKey: ["assessment"] });
    setViewNo(null);
    setEditing(false);
    setMessage(msg);
  };

  const restore = useMutation({
    mutationFn: (versionNo: number) =>
      unwrap(
        api.POST("/api/questions/{question_id}/restore/{version_no}", {
          params: { path: { question_id: id, version_no: versionNo } },
        }),
      ),
    onSuccess: (updated, versionNo) =>
      applyUpdate(updated, `Version ${versionNo} restored as version ${updated.current.version_no}.`),
  });

  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorNotice error={q.error} title="This question could not be loaded." />;
  const d = q.data;
  const viewing = d.versions.find((v) => v.version_no === viewNo) ?? d.current;
  const isCurrent = viewing.version_no === d.current.version_no;
  const inAssessments = d.assessment_ids.map((aid) => ({
    id: aid,
    title: assessments.data?.find((a) => a.id === aid)?.title ?? `Assessment ${aid}`,
  }));

  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-3 text-sm">
        <Link to="/questions">Question bank</Link>
      </nav>
      <PageHeader
        title={`Question ${d.id}`}
        lead={
          <span className="flex flex-wrap items-center gap-2">
            <CodeTag code={d.standard.code} course={d.standard.course_name} to={`/standards/${d.standard.id}`} />
            <StatusBadge status={d.status} />
            <DokBadge dok={d.current.dok} />
            <TypeBadge type={d.current.question_type} />
          </span>
        }
      />

      <div aria-live="polite" className="mb-4">
        {message ? <Notice>{message}</Notice> : null}
        <ErrorNotice error={restore.error} title="The version was not restored." />
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="min-w-0 space-y-5">
          {d.stimulus ? (
            <section className="panel p-4 sm:p-6" aria-label="Stimulus">
              <Stimulus body={d.stimulus.body} level={2} />
            </section>
          ) : null}

          <section className="panel p-4 sm:p-6" aria-labelledby="ver-h">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <h2 id="ver-h" className="flex flex-wrap items-center gap-2 text-lg font-bold">
                Version {viewing.version_no}
                {isCurrent ? <span className="text-sm font-normal text-muted">(current)</span> : null}
                <OriginBadge origin={viewing.origin} />
              </h2>
              {isCurrent && !editing ? (
                <button type="button" className="btn btn-sm" onClick={() => setEditing(true)}>
                  Edit question
                </button>
              ) : null}
            </div>
            {!isCurrent ? (
              <div className="mb-4">
                <Notice tone="info">
                  <p>
                    You are viewing an older version. Restoring it saves a copy as the newest version; nothing is
                    deleted.
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      disabled={restore.isPending}
                      onClick={() => restore.mutate(viewing.version_no)}
                    >
                      {restore.isPending ? "Restoring…" : `Restore version ${viewing.version_no}`}
                    </button>
                    <button type="button" className="btn btn-sm" onClick={() => setViewNo(null)}>
                      Back to current version
                    </button>
                  </div>
                </Notice>
              </div>
            ) : null}
            {editing && isCurrent ? (
              <EditQuestionForm
                key={d.current.id}
                questionId={d.id}
                base={d.current}
                onCancel={() => setEditing(false)}
                onSaved={(u) => applyUpdate(u, `Saved as version ${u.current.version_no}.`)}
              />
            ) : (
              <>
                <QuestionBody
                  stem={viewing.stem}
                  questionType={viewing.question_type}
                  choices={viewing.choices}
                  answer={viewing.answer}
                  explanation={viewing.explanation}
                  showKey
                />
                <p className="mt-4 text-sm text-muted">
                  {viewing.origin === "engine"
                    ? "The answer key and rationales were computed by the question family from the data set."
                    : "This version was edited by a teacher; the key reflects those edits."}
                  {viewing.change_note ? ` Change note: “${viewing.change_note}”` : ""}
                </p>
              </>
            )}
          </section>

          <Section title="Version history" id="hist-h">
            <ol className="divide-y divide-line-soft">
              {[...d.versions].reverse().map((v) => (
                <li key={v.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-2 font-bold">
                      Version {v.version_no}
                      {v.version_no === d.current.version_no ? (
                        <span className="text-sm font-normal text-muted">(current)</span>
                      ) : null}
                      <OriginBadge origin={v.origin} />
                    </p>
                    <p className="text-sm text-muted">
                      {formatDateTime(v.created_at)}, DOK {v.dok}, {TYPE_LABEL[v.question_type]}
                      {v.change_note ? `. “${v.change_note}”` : ""}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="btn btn-sm"
                      aria-pressed={viewing.version_no === v.version_no}
                      onClick={() => {
                        setEditing(false);
                        setViewNo(v.version_no === d.current.version_no ? null : v.version_no);
                      }}
                    >
                      View
                    </button>
                    {v.version_no !== d.current.version_no ? (
                      <button
                        type="button"
                        className="btn btn-sm"
                        disabled={restore.isPending}
                        onClick={() => restore.mutate(v.version_no)}
                      >
                        Restore
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          </Section>
        </div>

        <aside className="min-w-0 space-y-5">
          <StatusPanel q={d} onChanged={(u) => applyUpdate(u, `Status changed to ${STATUS_LABEL[u.status]}.`)} />
          <ProvenancePanel q={d} />
          <Section title="Used in assessments" id="used-h">
            {inAssessments.length === 0 ? (
              <p className="text-muted">Not in any assessment yet.</p>
            ) : (
              <ul className="space-y-1">
                {inAssessments.map((a) => (
                  <li key={a.id}>
                    <Link to={`/assessments/${a.id}`}>{a.title}</Link>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </aside>
      </div>
    </>
  );
}

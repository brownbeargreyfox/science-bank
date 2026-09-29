import { Link, useParams } from "react-router";
import { useStandard } from "../api/queries";
import { STATUSES } from "../api/types";
import {
  ErrorNotice,
  FamilyBadge,
  Hash,
  Loading,
  Meta,
  PageHeader,
  Pill,
  RepeatBadge,
  Section,
  StatusBadge,
} from "../components/ui";
import { formatDate, humanize } from "../lib/format";

export default function StandardDetailPage() {
  const id = Number(useParams().id);
  const q = useStandard(Number.isFinite(id) ? id : null);

  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorNotice error={q.error} title="This standard could not be loaded." />;
  const s = q.data;
  const src = s.source_document;
  const totalQuestions = Object.values(s.question_counts).reduce((a, b) => a + b, 0);
  const firstFamily = s.families[0];

  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-3 text-sm">
        <Link to={`/standards?course=${s.course_id}`}>Standards: {s.course_name}</Link>
      </nav>
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-3">
            <span>{s.code}</span>
            <span className="text-xl font-normal text-muted">
              {s.course_name}, {s.use_year}
            </span>
          </span>
        }
        lead={
          <span className="flex flex-wrap gap-2">
            <Pill>
              {s.domain_code}: {s.domain_name}
            </Pill>
            {s.families.length ? <FamilyBadge /> : null}
            {s.repeat_of_biology_1 ? <RepeatBadge /> : null}
          </span>
        }
        actions={
          firstFamily ? (
            <Link to={`/generate?standard=${s.id}&family=${firstFamily.key}`} className="btn btn-primary">
              Generate questions
            </Link>
          ) : null
        }
      />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-5">
          <section className="panel p-5" aria-labelledby="pe-h">
            <h2 id="pe-h" className="mb-2 text-sm font-bold text-muted">
              Performance expectation
            </h2>
            <p className="booklet max-w-[65ch] text-[1.25rem] leading-relaxed">{s.performance_expectation}</p>
            {s.clarification_statement ? (
              <div className="mt-4">
                <h3 className="font-bold">Clarification statement</h3>
                <p className="max-w-[70ch]">{s.clarification_statement}</p>
              </div>
            ) : null}
          </section>

          <section
            className="rounded-md border-2 border-bound bg-bound-soft p-5 text-ink"
            aria-labelledby="boundary-h"
          >
            <h2 id="boundary-h" className="mb-1 text-lg font-bold text-bound">
              State assessment boundary
            </h2>
            <p className="max-w-[70ch] text-[1.0625rem]">
              {s.state_assessment_boundary ?? "No assessment boundary is listed for this performance expectation."}
            </p>
          </section>

          <Section title="Dimensions" id="dims-h">
            <dl className="space-y-4">
              <div>
                <dt className="font-bold">Science and engineering practice: {s.sep.name}</dt>
                <dd className="max-w-[70ch] text-muted">{s.sep.description}</dd>
              </div>
              {s.dci.map((d) => (
                <div key={d.code}>
                  <dt className="font-bold">
                    Disciplinary core idea {d.code}: {d.name}
                  </dt>
                  <dd className="max-w-[70ch] text-muted">{d.text}</dd>
                </div>
              ))}
              <div>
                <dt className="font-bold">Crosscutting concept: {s.ccc.name}</dt>
                <dd className="max-w-[70ch] text-muted">{s.ccc.description}</dd>
              </div>
            </dl>
          </Section>

          <Section title="Observable performances" id="obs-h">
            <p className="mb-3 text-sm text-muted">
              What SCDE says students should be able to show. Each generated question cites one of these.
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              {Object.entries(s.observable_performances).map(([cat, items]) => (
                <div key={cat}>
                  <h3 className="mb-1 font-bold">{humanize(cat)}</h3>
                  <ul className="list-disc space-y-1 pl-5">
                    {items.map((t, i) => (
                      <li key={i}>{t}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </Section>

          {s.terminology.length ? (
            <Section title="Terminology" id="term-h">
              <ul className="flex flex-wrap gap-1.5">
                {s.terminology.map((t) => (
                  <li key={t}>
                    <Pill>{t}</Pill>
                  </li>
                ))}
              </ul>
            </Section>
          ) : null}

          {s.question_sentence_stems?.length ? (
            <Section title="Question sentence stems" id="stems-h">
              <ul className="list-disc space-y-1 pl-5">
                {s.question_sentence_stems.map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            </Section>
          ) : null}
        </div>

        <aside className="min-w-0 space-y-5">
          <Section title="Questions in the bank" id="counts-h">
            {totalQuestions === 0 ? (
              <p className="text-muted">None saved yet.</p>
            ) : (
              <ul className="space-y-1.5">
                {STATUSES.filter((st) => s.question_counts[st]).map((st) => (
                  <li key={st} className="flex items-center justify-between gap-2">
                    <StatusBadge status={st} />
                    <Link to={`/questions?standard=${s.id}&course=${s.course_id}&status=${st}`}>
                      {s.question_counts[st]} questions
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            {s.families.length ? (
              <div className="mt-4 space-y-2 border-t border-line-soft pt-3">
                {s.families.map((f) => (
                  <div key={f.key}>
                    <p className="font-bold">{f.title}</p>
                    <p className="text-sm text-muted">Family version {f.version}</p>
                    <Link to={`/generate?standard=${s.id}&family=${f.key}`} className="text-sm font-bold">
                      Generate from this family
                    </Link>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted">No question family is written for this standard yet.</p>
            )}
          </Section>

          <Section title="Bundles" id="bundles-h">
            {s.bundles.length === 0 ? (
              <p className="text-muted">Not part of any bundle.</p>
            ) : (
              <ul className="space-y-1.5">
                {s.bundles.map((b) => (
                  <li key={b.id}>
                    <Link to={`/bundles?course=${s.course_id}#bundle-${b.id}`}>{b.name}</Link>
                    {b.partial ? <span className="ml-2 text-sm text-muted">(partial)</span> : null}
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Source" id="src-h">
            <dl>
              <Meta label="Document">{src.title}</Meta>
              <Meta label="Authority">{src.authority ?? "Not recorded"}</Meta>
              <Meta label="Published">{formatDate(src.published) || "Not recorded"}</Meta>
              <Meta label="Use year">{src.use_year ?? s.use_year}</Meta>
              <Meta label="Data file">
                <code className="text-sm break-all">{src.data_file ?? "Not recorded"}</code>
              </Meta>
              <Meta label="File sha256">
                <Hash value={src.content_sha256} />
              </Meta>
              <Meta label="Standard sha256">
                <Hash value={s.content_sha256} />
              </Meta>
              <Meta label="SCDE page">
                {src.url ? (
                  <a href={src.url} target="_blank" rel="noreferrer" className="break-all">
                    {src.url}
                  </a>
                ) : (
                  "Not recorded"
                )}
              </Meta>
            </dl>
          </Section>

        </aside>
      </div>
    </>
  );
}

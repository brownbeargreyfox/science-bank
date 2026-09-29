import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api, unwrap } from "../api/client";
import { formatDate } from "../lib/format";
import { accuracyText } from "../lib/results";
import { ErrorNotice, Loading, Pill, Section } from "./ui";

const PAGE = 10;

export default function UsagePanel({ questionId }: { questionId: number }) {
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["usage", questionId, offset],
    queryFn: () => unwrap(api.GET("/api/questions/{question_id}/usage", { params: { path: { question_id: questionId }, query: { limit: PAGE, offset } } })),
  });
  return <Section title="Class results" id="usage-h">
    {query.isPending ? <Loading /> : null}<ErrorNotice error={query.error} />
    {query.data ? <>
      {query.data.total === 0 ? <p className="text-sm text-muted">Not recorded in any of your uses yet.</p> : <ul className="divide-y divide-line-soft">{query.data.items.map((use) => <li key={use.administration_id} className="py-2 text-sm"><Link to={`/administrations/${use.administration_id}`} className="font-bold">{use.label}</Link>{" "}<span className="text-muted">{formatDate(use.administered_on)}, {use.assessment_title}. Version {use.pinned_version_no}{use.is_current_version ? " (current)" : " (an earlier version)"}.</span><div className="tabular-nums">{use.attempted > 0 ? `${use.correct} / ${use.attempted}` : "No data"} {accuracyText(use.correct, use.attempted)} {use.limited_responses ? <Pill>Limited response count</Pill> : null}</div></li>)}</ul>}
      {query.data.total > PAGE ? <div className="mt-2 flex gap-2"><button type="button" className="btn btn-sm" disabled={offset === 0} onClick={() => setOffset(offset - PAGE)}>Newer</button><button type="button" className="btn btn-sm" disabled={offset + PAGE >= query.data.total} onClick={() => setOffset(offset + PAGE)}>Older</button></div> : null}
      {query.data.parent || query.data.variants.length ? <div className="mt-3 text-sm">{query.data.parent ? <p>Variant of <Link to={`/questions/${query.data.parent.id}`}>question {query.data.parent.id}</Link>.</p> : null}{query.data.variants.length ? <p>New generated items from this one: {query.data.variants.map((variant, index) => <span key={variant.id}>{index ? ", " : ""}<Link to={`/questions/${variant.id}`}>{variant.id}</Link></span>)}.</p> : null}<p className="text-muted">A variant is a new generated item from the same family and template. Its results are recorded separately from the original’s.</p></div> : null}
    </> : null}
  </Section>;
}

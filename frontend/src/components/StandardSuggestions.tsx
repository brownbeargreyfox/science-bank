import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api, unwrap } from "../api/client";
import { useFamilies, useStandard, useStandards } from "../api/queries";
import type { StandardSummary } from "../api/types";
import { ErrorNotice, Loading } from "./ui";

function short(text: string) { return text.length > 110 ? `${text.slice(0, 107)}…` : text; }

function SuggestionRow({ standard, bundleId, familyKeys }: { standard: StandardSummary; bundleId?: number; familyKeys: (id: number) => string[] }) {
  const keys = familyKeys(standard.id); const query = new URLSearchParams({ standard: String(standard.id) });
  if (bundleId) query.set("bundle", String(bundleId)); if (keys.length === 1) query.set("family", keys[0]);
  return <li className="border-t border-line-soft py-2 first:border-t-0"><div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0"><code className="font-bold">{standard.code}</code><p className="text-sm text-muted">{short(standard.performance_expectation)}</p></div>{keys.length ? <Link className="btn btn-sm btn-primary" to={`/generate?${query}`}>Generate</Link> : <Link className="btn btn-sm" to={`/standards/${standard.id}`}>No generator yet</Link>}</div></li>;
}

export function StandardSuggestions({ standardId, bundleId }: { standardId: number | null; bundleId: number | null }) {
  const standard = useStandard(standardId);
  const families = useFamilies();
  const bundles = useQuery({ queryKey: ["bundles", "suggestions", standard.data?.course_id], queryFn: () => unwrap(api.GET("/api/bundles", { params: { query: { course_id: standard.data?.course_id ?? null } } })), enabled: standard.data !== undefined });
  const domain = useStandards({ course_id: standard.data?.course_id ?? null, domain: standard.data?.domain_code ?? null }, standard.data !== undefined);
  if (standardId === null) return null;
  if (standard.isPending || families.isPending) return <aside className="mt-5 lg:mt-0"><Loading label="Loading related standards…" /></aside>;
  if (standard.error || families.error || bundles.error || domain.error) return <aside className="mt-5 lg:mt-0"><ErrorNotice error={standard.error ?? families.error ?? bundles.error ?? domain.error} /></aside>;
  const current = standard.data; if (!current) return null;
  const selectedBundle = bundles.data?.find((item) => item.id === bundleId) ?? bundles.data?.find((item) => current.bundles.some((ref) => ref.id === item.id));
  const siblings = (selectedBundle?.aligned ?? []).filter((item) => item.standard_id !== current.id).map((item) => ({ id: item.standard_id, code: item.code, performance_expectation: item.performance_expectation, course_id: current.course_id, course_name: current.course_name, course_slug: current.course_slug, domain_code: current.domain_code, domain_name: current.domain_name, families: [], question_family_candidate: false, repeat_of_biology_1: false, topics: [], use_year: current.use_year }));
  const siblingIds = new Set(siblings.map((item) => item.id));
  const domainItems = (domain.data ?? []).filter((item) => item.id !== current.id && !siblingIds.has(item.id));
  const keys = (id: number) => (families.data ?? []).filter((family) => family.bindings.some((binding) => binding.standard_ids.includes(id))).map((family) => family.key);
  if (!siblings.length && !domainItems.length) return null;
  return <aside className="space-y-4"><h2 className="text-lg font-bold">Related standards</h2>{siblings.length ? <section className="panel p-4" aria-labelledby="also-bundle"><h3 id="also-bundle" className="mb-2 font-bold">Also in this bundle</h3><ul><>{siblings.map((item) => <SuggestionRow key={item.id} standard={item} bundleId={selectedBundle?.id} familyKeys={keys} />)}</></ul></section> : null}{domainItems.length ? <section className="panel p-4" aria-labelledby="same-domain"><h3 id="same-domain" className="mb-2 font-bold">Same domain</h3><ul>{domainItems.map((item) => <SuggestionRow key={item.id} standard={item} bundleId={selectedBundle?.id} familyKeys={keys} />)}</ul></section> : null}</aside>;
}

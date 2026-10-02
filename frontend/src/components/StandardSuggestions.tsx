import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api, unwrap } from "../api/client";
import { useFamilies, useStandard, useStandards } from "../api/queries";
import { ErrorNotice, Loading } from "./ui";

interface Suggestion {
  id: number;
  code: string;
  performance_expectation: string;
}

function short(text: string) {
  return text.length > 110 ? `${text.slice(0, 107)}…` : text;
}

function SuggestionRow({
  standard,
  bundleId,
  familyKeys,
}: {
  standard: Suggestion;
  bundleId?: number;
  familyKeys: (id: number) => string[];
}) {
  const keys = familyKeys(standard.id);
  const query = new URLSearchParams({ standard: String(standard.id) });
  if (bundleId) query.set("bundle", String(bundleId));
  if (keys.length === 1) query.set("family", keys[0]);
  return (
    <li className="border-t border-line-soft py-2 first:border-t-0">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <code className="font-bold">{standard.code}</code>
          <p className="text-sm text-muted">{short(standard.performance_expectation)}</p>
        </div>
        {keys.length ? (
          <Link className="btn btn-sm btn-primary" to={`/generate?${query}`}>
            Generate
          </Link>
        ) : (
          <Link className="btn btn-sm" to={`/standards/${standard.id}`}>
            No generator yet
          </Link>
        )}
      </div>
    </li>
  );
}

function Group({
  id,
  title,
  items,
  bundleId,
  familyKeys,
}: {
  id: string;
  title: string;
  items: Suggestion[];
  bundleId?: number;
  familyKeys: (id: number) => string[];
}) {
  return (
    <section className="panel min-w-0 p-4" aria-labelledby={id}>
      <h3 id={id} className="mb-2 font-bold">
        {title}
      </h3>
      <ul>
        {items.map((item) => (
          <SuggestionRow key={item.id} standard={item} bundleId={bundleId} familyKeys={familyKeys} />
        ))}
      </ul>
    </section>
  );
}

/** Other standards worth generating next: the rest of the bundle that sent you here, then the same domain. */
export function StandardSuggestions({ standardId, bundleId }: { standardId: number | null; bundleId: number | null }) {
  const standard = useStandard(standardId);
  const families = useFamilies();
  const current = standard.data;
  const bundles = useQuery({
    queryKey: ["bundles", current?.course_id],
    queryFn: () => unwrap(api.GET("/api/bundles", { params: { query: { course_id: current?.course_id ?? null } } })),
    enabled: current !== undefined,
    staleTime: 5 * 60_000,
  });
  const domain = useStandards(
    { course_id: current?.course_id ?? null, domain: current?.domain_code ?? null },
    current !== undefined,
  );
  if (standardId === null) return null;
  const error = standard.error ?? families.error ?? bundles.error ?? domain.error;
  if (error)
    return (
      <div className="mt-5">
        <ErrorNotice error={error} />
      </div>
    );
  if (!current || families.isPending || bundles.isPending || domain.isPending)
    return (
      <div className="mt-5">
        <Loading label="Loading related standards…" />
      </div>
    );

  const bundle =
    bundles.data?.find((item) => item.id === bundleId) ??
    bundles.data?.find((item) => current.bundles.some((ref) => ref.id === item.id));
  const siblings: Suggestion[] = (bundle?.aligned ?? [])
    .filter((item) => item.standard_id !== current.id)
    .map((item) => ({ id: item.standard_id, code: item.code, performance_expectation: item.performance_expectation }));
  const listed = new Set(siblings.map((item) => item.id));
  const sameDomain: Suggestion[] = (domain.data ?? []).filter((item) => item.id !== current.id && !listed.has(item.id));
  if (!siblings.length && !sameDomain.length) return null;

  const familyKeys = (id: number) =>
    (families.data ?? [])
      .filter((family) => family.bindings.some((binding) => binding.standard_ids.includes(id)))
      .map((family) => family.key);
  return (
    <section className="mt-5" aria-labelledby="related-standards">
      <h2 id="related-standards" className="mb-3 text-lg font-bold">
        Related standards
      </h2>
      <div className="grid gap-4 md:grid-cols-2">
        {siblings.length ? (
          <Group
            id="also-in-bundle"
            title="Also in this bundle"
            items={siblings}
            bundleId={bundle?.id}
            familyKeys={familyKeys}
          />
        ) : null}
        {sameDomain.length ? (
          <Group
            id="same-domain"
            title="Same domain"
            items={sameDomain}
            bundleId={bundle?.id}
            familyKeys={familyKeys}
          />
        ) : null}
      </div>
    </section>
  );
}

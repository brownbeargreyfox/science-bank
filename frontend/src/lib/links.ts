/** Builds the Generate URL used by "Regenerate this set" links. */
export function generateUrl(req: {
  course_id?: number | null;
  standard_id: number;
  family_key: string;
  seed?: string | null;
  doks?: number[];
  question_types?: string[];
  template_keys?: string[];
  quantity?: number;
  preview?: boolean;
}): string {
  const p = new URLSearchParams();
  if (req.course_id) p.set("course", String(req.course_id));
  p.set("standard", String(req.standard_id));
  p.set("family", req.family_key);
  if (req.doks?.length) p.set("doks", req.doks.join(","));
  if (req.question_types?.length) p.set("types", req.question_types.join(","));
  if (req.template_keys?.length) p.set("templates", req.template_keys.join(","));
  if (req.quantity) p.set("quantity", String(req.quantity));
  if (req.seed) p.set("seed", req.seed);
  if (req.preview) p.set("preview", "1");
  return `/generate?${p.toString()}`;
}

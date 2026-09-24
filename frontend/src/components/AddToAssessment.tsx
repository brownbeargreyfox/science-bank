import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { api, unwrap } from "../api/client";
import { queryClient, useAssessments } from "../api/queries";
import type { AddItemsOut } from "../api/types";
import { ErrorNotice, Notice } from "./ui";
import { pluralize } from "../lib/format";

export function SkippedList({ skipped }: { skipped: Record<string, string> }) {
  const entries = Object.entries(skipped);
  if (!entries.length) return null;
  return (
    <div className="mt-2">
      <p className="font-bold">{pluralize(entries.length, "question")} skipped:</p>
      <ul className="list-disc pl-5">
        {entries.map(([id, reason]) => (
          <li key={id}>
            <Link to={`/questions/${id}`}>#{id}</Link>: {reason}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Adds question ids to an existing assessment, or creates a new one first. */
export function AddToAssessment({ questionIds, onDone }: { questionIds: number[]; onDone?: () => void }) {
  const assessments = useAssessments();
  const [target, setTarget] = useState<string>("");
  const [newTitle, setNewTitle] = useState("");
  const [result, setResult] = useState<{ id: number; title: string; out: AddItemsOut } | null>(null);

  const add = useMutation({
    mutationFn: async () => {
      let id: number;
      let title: string;
      if (target === "new") {
        const created = await unwrap(api.POST("/api/assessments", { body: { title: newTitle.trim(), instructions: "" } }));
        id = created.id;
        title = created.title;
      } else {
        id = Number(target);
        title = assessments.data?.find((a) => a.id === id)?.title ?? `Assessment ${id}`;
      }
      const out = await unwrap(
        api.POST("/api/assessments/{assessment_id}/items", {
          params: { path: { assessment_id: id } },
          body: { question_ids: questionIds },
        }),
      );
      return { id, title, out };
    },
    onSuccess: (r) => {
      setResult(r);
      void queryClient.invalidateQueries({ queryKey: ["assessments"] });
      void queryClient.invalidateQueries({ queryKey: ["assessment", r.id] });
      void queryClient.invalidateQueries({ queryKey: ["question"] });
      onDone?.();
    },
  });

  const valid = questionIds.length > 0 && (target === "new" ? newTitle.trim().length > 0 : target !== "");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (valid) add.mutate();
  };

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
      <div className="min-w-[12rem] flex-1">
        <label htmlFor="ata-target" className="field-label">
          Add to assessment
        </label>
        <select id="ata-target" className="input" value={target} onChange={(e) => setTarget(e.target.value)}>
          <option value="">Choose an assessment…</option>
          {assessments.data?.filter((a) => a.can_modify).map((a) => (
            <option key={a.id} value={a.id}>
              {a.title} ({pluralize(a.item_count, "item")})
            </option>
          ))}
          <option value="new">New assessment…</option>
        </select>
      </div>
      {target === "new" ? (
        <div className="min-w-[12rem] flex-1">
          <label htmlFor="ata-title" className="field-label">
            New assessment title
          </label>
          <input id="ata-title" className="input" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />
        </div>
      ) : null}
      <button type="submit" className="btn btn-primary" disabled={!valid || add.isPending}>
        {add.isPending ? "Adding…" : `Add ${pluralize(questionIds.length, "question")}`}
      </button>
      <div aria-live="polite" className="basis-full">
        <ErrorNotice error={add.error} title="Nothing was added." />
        {result ? (
          <Notice tone={Object.keys(result.out.skipped).length ? "warn" : "ok"}>
            <p>
              Added {pluralize(result.out.added.length, "question")} to{" "}
              <Link to={`/assessments/${result.id}`} className="font-bold">
                {result.title}
              </Link>
              .
            </p>
            <SkippedList skipped={result.out.skipped} />
          </Notice>
        ) : null}
      </div>
    </form>
  );
}

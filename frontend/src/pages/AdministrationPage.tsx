import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";
import { api, unwrap } from "../api/client";
import { queryClient } from "../api/queries";
import type { AdministrationDetail } from "../api/types";
import { ConfirmDialog, ErrorNotice, Loading, Notice, PageHeader, Pill, Section } from "../components/ui";
import { formatDate } from "../lib/format";
import { accuracyText, limitedResponses, parseCell, sumCells, type CellInput, type CellState } from "../lib/results";

const EMPTY: CellInput = { correct: "", attempted: "" };
const cellKey = (sectionId: number, itemId: number) => `${sectionId}:${itemId}`;

function savedCells(detail: AdministrationDetail): Record<string, CellInput> {
  return Object.fromEntries(
    detail.results.map((result) => [
      cellKey(result.section_id, result.item_id),
      { correct: String(result.correct), attempted: String(result.attempted) },
    ]),
  );
}

export default function AdministrationPage() {
  const id = Number(useParams().id);
  const query = useQuery({
    queryKey: ["administration", id],
    queryFn: () =>
      unwrap(api.GET("/api/administrations/{administration_id}", { params: { path: { administration_id: id } } })),
  });
  if (query.isPending) return <Loading />;
  if (query.isError) return <ErrorNotice error={query.error} />;
  return <Grid key={query.dataUpdatedAt} detail={query.data} />;
}

function Grid({ detail }: { detail: AdministrationDetail }) {
  const saved = useMemo(() => savedCells(detail), [detail]);
  const [cells, setCells] = useState<Record<string, CellInput>>(saved);
  const [newSection, setNewSection] = useState("");
  const [removing, setRemoving] = useState<{ id: number; name: string } | null>(null);
  const cell = (sectionId: number, itemId: number): CellInput => cells[cellKey(sectionId, itemId)] ?? EMPTY;
  const setField = (sectionId: number, itemId: number, field: keyof CellInput, value: string) =>
    setCells((previous) => ({
      ...previous,
      [cellKey(sectionId, itemId)]: { ...(previous[cellKey(sectionId, itemId)] ?? EMPTY), [field]: value },
    }));
  const states = new Map<string, CellState>();
  for (const section of detail.sections)
    for (const item of detail.items) states.set(cellKey(section.id, item.id), parseCell(cell(section.id, item.id)));
  const anyInvalid = [...states.values()].some((state) => state.kind === "invalid");
  const changed = detail.sections.flatMap((section) =>
    detail.items
      .filter((item) => {
        const now = cell(section.id, item.id);
        const was = saved[cellKey(section.id, item.id)] ?? EMPTY;
        return now.correct.trim() !== was.correct || now.attempted.trim() !== was.attempted;
      })
      .map((item) => ({ section, item })),
  );
  const refresh = (fresh: AdministrationDetail) => {
    queryClient.setQueryData(["administration", detail.id], fresh);
    void queryClient.invalidateQueries({ queryKey: ["results"] });
    void queryClient.invalidateQueries({ queryKey: ["administrations"] });
    void queryClient.invalidateQueries({ queryKey: ["usage"] });
  };
  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.PUT("/api/administrations/{administration_id}/results", {
          params: { path: { administration_id: detail.id } },
          body: {
            rows: changed.map(({ section, item }) => {
              const state = states.get(cellKey(section.id, item.id))!;
              return state.kind === "valid"
                ? { section_id: section.id, item_id: item.id, correct: state.correct, attempted: state.attempted }
                : { section_id: section.id, item_id: item.id, correct: null, attempted: null };
            }),
          },
        }),
      ),
    onSuccess: refresh,
  });
  const addSection = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/administrations/{administration_id}/sections", {
          params: { path: { administration_id: detail.id } },
          body: { name: newSection.trim() },
        }),
      ),
    onSuccess: refresh,
  });
  const removeSection = useMutation({
    mutationFn: (sectionId: number) =>
      unwrap(
        api.DELETE("/api/administrations/{administration_id}/sections/{section_id}", {
          params: { path: { administration_id: detail.id, section_id: sectionId } },
        }),
      ),
    onSuccess: refresh,
  });
  const submitSection = (event: FormEvent) => {
    event.preventDefault();
    if (newSection.trim()) addSection.mutate();
  };
  return (
    <>
      <PageHeader
        title={detail.label}
        lead={
          <>
            {detail.assessment_title}, given {formatDate(detail.administered_on)}.{" "}
            <Link to={`/assessments/${detail.assessment_id}`}>Back to the assessment</Link>
          </>
        }
      />
      <Notice tone="info">
        “Correct” means students who earned full credit; partial credit is not supported yet. Leave a cell blank when
        you have no data. Blank is different from 0.
      </Notice>
      <div className="my-3 flex flex-wrap items-center gap-3" aria-live="polite">
        <button
          type="button"
          className="btn btn-primary"
          disabled={anyInvalid || changed.length === 0 || save.isPending}
          onClick={() => save.mutate()}
        >
          {save.isPending ? "Saving…" : "Save results"}
        </button>
        {anyInvalid ? <span className="text-sm text-red-700">Fix the highlighted cells to save.</span> : null}
        {!anyInvalid && changed.length > 0 ? <span className="text-sm text-muted">Unsaved changes</span> : null}
        <ErrorNotice error={save.error ?? addSection.error ?? removeSection.error} />
      </div>
      <div className="panel mb-5 relative overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">Correct and attempted counts by question and section</caption>
          <thead>
            <tr className="border-b border-line-soft text-left">
              <th scope="col" className="p-3">
                Question
              </th>
              {detail.sections.map((section) => (
                <th key={section.id} scope="col" className="p-3">
                  {section.name}
                </th>
              ))}
              <th scope="col" className="p-3">
                All sections
              </th>
            </tr>
          </thead>
          <tbody>
            {detail.items.map((item) => {
              const total = sumCells(detail.sections.map((section) => states.get(cellKey(section.id, item.id))!));
              return (
                <tr key={item.id} className="border-b border-line-soft align-top">
                  <th scope="row" className="min-w-56 p-3 text-left font-normal">
                    <span className="font-bold">{item.position}.</span> {item.stem.slice(0, 110)}
                    {item.stem.length > 110 ? "…" : ""}
                    <div className="text-xs text-muted">
                      {item.standard_code}, DOK {item.dok}, version {item.pinned_version_no}
                    </div>
                  </th>
                  {detail.sections.map((section) => {
                    const current = cell(section.id, item.id);
                    const state = states.get(cellKey(section.id, item.id))!;
                    const errorId = `err-${section.id}-${item.id}`;
                    const invalid = state.kind === "invalid";
                    return (
                      <td key={section.id} className="p-3">
                        <div className="flex items-center gap-1">
                          <input
                            className="input w-16"
                            inputMode="numeric"
                            aria-label={`${section.name}, Question ${item.position}, correct`}
                            aria-invalid={invalid}
                            aria-describedby={invalid ? errorId : undefined}
                            value={current.correct}
                            onChange={(event) => setField(section.id, item.id, "correct", event.target.value)}
                          />
                          <span aria-hidden="true">/</span>
                          <input
                            className="input w-16"
                            inputMode="numeric"
                            aria-label={`${section.name}, Question ${item.position}, attempted`}
                            aria-invalid={invalid}
                            aria-describedby={invalid ? errorId : undefined}
                            value={current.attempted}
                            onChange={(event) => setField(section.id, item.id, "attempted", event.target.value)}
                          />
                        </div>
                        {invalid ? (
                          <p id={errorId} className="mt-1 text-xs text-red-700">
                            {state.message}
                          </p>
                        ) : null}
                      </td>
                    );
                  })}
                  <td className="p-3 tabular-nums">
                    <div className="font-bold">
                      {total.attempted > 0 ? `${total.correct} / ${total.attempted}` : "—"}
                    </div>
                    <div>{accuracyText(total.correct, total.attempted)}</div>
                    {limitedResponses(total.attempted) ? <Pill>Limited response count</Pill> : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <Section title="Sections" id="sections-h">
        <ul className="mb-3 flex flex-wrap gap-2">
          {detail.sections.map((section) => (
            <li key={section.id} className="flex items-center gap-2 rounded border border-line-soft px-2 py-1">
              {section.name}
              {detail.sections.length > 1 ? (
                <button
                  type="button"
                  className="btn btn-sm btn-danger"
                  disabled={removeSection.isPending}
                  onClick={() => setRemoving({ id: section.id, name: section.name })}
                >
                  Remove
                </button>
              ) : null}
            </li>
          ))}
        </ul>
        <form onSubmit={submitSection} className="flex flex-wrap items-end gap-2">
          <div>
            <label htmlFor="new-section" className="field-label">
              Add a section
            </label>
            <input
              id="new-section"
              className="input"
              value={newSection}
              placeholder="Period 6"
              onChange={(event) => setNewSection(event.target.value)}
            />
          </div>
          <button type="submit" className="btn" disabled={!newSection.trim() || addSection.isPending}>
            Add section
          </button>
        </form>
      </Section>
      <ConfirmDialog
        open={removing !== null}
        title={removing ? `Remove “${removing.name}”?` : ""}
        confirmLabel="Remove section"
        pending={removeSection.isPending}
        onCancel={() => setRemoving(null)}
        onConfirm={() => {
          if (removing) removeSection.mutate(removing.id, { onSettled: () => setRemoving(null) });
        }}
      >
        <p>This also deletes every result entered for this section.</p>
        {changed.length ? <p className="mt-2">Unsaved changes on this page will be lost.</p> : null}
      </ConfirmDialog>
    </>
  );
}

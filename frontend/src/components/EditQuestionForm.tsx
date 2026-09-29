import { useMutation } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { api, unwrap } from "../api/client";
import type { ChoiceIn, QuestionDetail, QuestionVersion } from "../api/types";
import { ErrorNotice } from "./ui";

const LETTERS = "ABCDE";

export function EditQuestionForm({
  questionId,
  base,
  onSaved,
  onCancel,
}: {
  questionId: number;
  base: QuestionVersion;
  onSaved: (q: QuestionDetail) => void;
  onCancel: () => void;
}) {
  const uid = useId();
  const isMC = base.question_type === "multiple_choice";
  const [stem, setStem] = useState(base.stem);
  const [dok, setDok] = useState(base.dok);
  const [choices, setChoices] = useState<ChoiceIn[]>(
    base.choices.map((c) => ({ text: c.text, correct: c.correct, rationale: c.rationale })),
  );
  const [answer, setAnswer] = useState(base.answer);
  const [explanation, setExplanation] = useState(base.explanation);
  const [note, setNote] = useState("");

  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/questions/{question_id}/versions", {
          params: { path: { question_id: questionId } },
          body: {
            stem,
            dok,
            explanation,
            change_note: note.trim() || null,
            ...(isMC ? { choices } : { answer, choices: [] }),
          },
        }),
      ),
    onSuccess: onSaved,
  });

  const setChoice = (i: number, patch: Partial<ChoiceIn>) =>
    setChoices((cs) => cs.map((c, j) => (j === i ? { ...c, ...patch } : c)));
  const markCorrect = (i: number) => setChoices((cs) => cs.map((c, j) => ({ ...c, correct: j === i })));
  const removeChoice = (i: number) => setChoices((cs) => cs.filter((_, j) => j !== i));
  const addChoice = () => setChoices((cs) => [...cs, { text: "", correct: false, rationale: "" }]);

  const correctCount = choices.filter((c) => c.correct).length;
  const problems: string[] = [];
  if (!stem.trim()) problems.push("Write a stem.");
  if (isMC) {
    if (choices.length < 2 || choices.length > 5) problems.push("Use 2 to 5 choices.");
    if (correctCount !== 1) problems.push("Mark exactly one choice as correct.");
    if (choices.some((c) => !c.text.trim())) problems.push("Every choice needs text.");
  } else if (!answer.trim()) {
    problems.push("Write an exemplar answer.");
  }

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (problems.length === 0) save.mutate();
  };

  return (
    <form onSubmit={submit} className="space-y-4" aria-label="Edit question">
      <div>
        <label htmlFor={`${uid}-stem`} className="field-label">
          Stem
        </label>
        <textarea id={`${uid}-stem`} className="input booklet" rows={4} value={stem} onChange={(e) => setStem(e.target.value)} />
      </div>
      <div className="max-w-[10rem]">
        <label htmlFor={`${uid}-dok`} className="field-label">
          DOK
        </label>
        <select id={`${uid}-dok`} className="input" value={dok} onChange={(e) => setDok(Number(e.target.value))}>
          {[1, 2, 3, 4].map((d) => (
            <option key={d} value={d}>
              DOK {d}
            </option>
          ))}
        </select>
      </div>

      {isMC ? (
        <fieldset>
          <legend className="field-label">Choices</legend>
          <p className="hint mb-2">Select the radio button beside the correct choice. Letters are reassigned in order when you save.</p>
          <ol className="space-y-3">
            {choices.map((c, i) => (
              <li key={i} className={`rounded-md border p-3 ${c.correct ? "border-mark-edge bg-[#fffbea]" : "border-line"}`}>
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <label className="flex items-center gap-2 font-bold">
                    <input
                      type="radio"
                      name={`${uid}-correct`}
                      className="check"
                      checked={c.correct}
                      onChange={() => markCorrect(i)}
                    />
                    Choice {LETTERS[i]} {c.correct ? "(correct)" : ""}
                  </label>
                  <button
                    type="button"
                    className="btn btn-sm btn-danger"
                    onClick={() => removeChoice(i)}
                    disabled={choices.length <= 2}
                    aria-label={`Remove choice ${LETTERS[i]}`}
                  >
                    Remove
                  </button>
                </div>
                <label htmlFor={`${uid}-c${i}`} className="sr-only">
                  Choice {LETTERS[i]} text
                </label>
                <input
                  id={`${uid}-c${i}`}
                  className="input booklet mb-2"
                  value={c.text}
                  placeholder="Choice text"
                  onChange={(e) => setChoice(i, { text: e.target.value })}
                />
                <label htmlFor={`${uid}-r${i}`} className="text-sm font-bold text-muted">
                  Rationale for choice {LETTERS[i]}
                </label>
                <textarea
                  id={`${uid}-r${i}`}
                  className="input mt-1"
                  rows={2}
                  value={c.rationale ?? ""}
                  onChange={(e) => setChoice(i, { rationale: e.target.value })}
                />
              </li>
            ))}
          </ol>
          <button type="button" className="btn btn-sm mt-3" onClick={addChoice} disabled={choices.length >= 5}>
            Add a choice
          </button>
        </fieldset>
      ) : (
        <div>
          <label htmlFor={`${uid}-answer`} className="field-label">
            Exemplar answer
          </label>
          <textarea id={`${uid}-answer`} className="input" rows={5} value={answer} onChange={(e) => setAnswer(e.target.value)} />
        </div>
      )}

      <div>
        <label htmlFor={`${uid}-expl`} className="field-label">
          {isMC ? "Explanation" : "Scoring guide"}
        </label>
        <textarea id={`${uid}-expl`} className="input" rows={4} value={explanation} onChange={(e) => setExplanation(e.target.value)} />
      </div>
      <div>
        <label htmlFor={`${uid}-note`} className="field-label">
          Change note <span className="font-normal text-muted">(optional)</span>
        </label>
        <input
          id={`${uid}-note`}
          className="input"
          value={note}
          placeholder="What you changed and why"
          onChange={(e) => setNote(e.target.value)}
        />
      </div>

      <div aria-live="polite">
        {problems.length ? (
          <ul className="list-disc pl-5 text-sm font-bold text-bound">
            {problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        ) : null}
        <ErrorNotice error={save.error} title="The new version was not saved." />
      </div>

      <div className="flex flex-wrap gap-2">
        <button type="submit" className="btn btn-primary" disabled={problems.length > 0 || save.isPending}>
          {save.isPending ? "Saving…" : "Save as new version"}
        </button>
        <button type="button" className="btn" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

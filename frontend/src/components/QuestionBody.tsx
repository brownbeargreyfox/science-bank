import type { ReactNode } from "react";

export interface ChoiceLike {
  label: string;
  text: string;
  correct?: boolean | null;
  rationale?: string | null;
}

/**
 * Stem + choices in the student-facing serif voice. With `showKey`, the correct
 * choice gets a highlighter mark, a border and a "Correct answer" label (the
 * label and border survive black-and-white printing), and each rationale shows.
 */
export function QuestionBody({
  stem,
  questionType,
  choices,
  answer,
  explanation,
  showKey,
  number,
  answerLines = 0,
  meta,
}: {
  stem: string;
  questionType: "multiple_choice" | "constructed_response";
  choices: ChoiceLike[];
  answer?: string | null;
  explanation?: string | null;
  showKey: boolean;
  number?: number;
  answerLines?: number;
  meta?: ReactNode;
}) {
  return (
    <div className="booklet">
      <div className="flex gap-2">
        {number !== undefined ? <span className="font-semibold tabular-nums">{number}.</span> : null}
        <div className="min-w-0 flex-1">
          <div className="q-core">
            <p className="max-w-[70ch] whitespace-pre-line">{stem}</p>
            {meta}
            {questionType === "multiple_choice" ? (
              <ol className="mt-2 space-y-1.5" aria-label="Answer choices">
                {choices.map((c) => {
                  const correct = showKey && c.correct === true;
                  return (
                    <li
                      key={c.label}
                      className={`rounded px-2 py-1 ${correct ? "choice-correct" : ""}`}
                    >
                      <div className="flex gap-2">
                        <span className="w-6 flex-none font-semibold">{c.label}.</span>
                        <span className="min-w-0 flex-1">
                          {c.text}
                          {correct ? (
                            <strong className="ml-2 whitespace-nowrap font-sans text-sm">✓ Correct answer</strong>
                          ) : null}
                        </span>
                      </div>
                      {showKey && c.rationale ? (
                        <p className="mt-0.5 ml-8 font-sans text-[0.9rem] leading-snug text-muted print:text-black">
                          {c.rationale}
                        </p>
                      ) : null}
                    </li>
                  );
                })}
              </ol>
            ) : null}
          </div>
          {questionType === "constructed_response" && answerLines > 0 ? (
            <div className="mt-3" aria-label="Space for the answer">
              {Array.from({ length: answerLines }, (_, i) => (
                <div key={i} className="answer-line" />
              ))}
            </div>
          ) : null}
          {showKey && (answer || explanation) ? (
            <div className="mt-3 space-y-2 border-l-4 border-petrol pl-3 font-sans text-[0.9375rem] print:border-black">
              {answer && questionType === "constructed_response" ? (
                <div>
                  <p className="font-bold">Exemplar answer</p>
                  <p className="whitespace-pre-line">{answer}</p>
                </div>
              ) : null}
              {answer && questionType === "multiple_choice" ? (
                <p>
                  <span className="font-bold">Answer: </span>
                  {answer}
                </p>
              ) : null}
              {explanation ? (
                <div>
                  <p className="font-bold">{questionType === "constructed_response" ? "Scoring guide" : "Explanation"}</p>
                  <p className="whitespace-pre-line">{explanation}</p>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

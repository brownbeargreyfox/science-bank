/** Result-grid rules. Blank is "no data", never 0; attempted >= 1; 0 <= correct <= attempted. */

export const LIMITED_RESPONSE_THRESHOLD = 10;

export interface CellInput {
  correct: string;
  attempted: string;
}

export type CellState =
  { kind: "empty" } | { kind: "invalid"; message: string } | { kind: "valid"; correct: number; attempted: number };

const WHOLE_NUMBER = /^\d+$/;

export function parseCell(input: CellInput): CellState {
  const correct = input.correct.trim();
  const attempted = input.attempted.trim();
  if (correct === "" && attempted === "") return { kind: "empty" };
  if (correct === "" || attempted === "") {
    return { kind: "invalid", message: "Enter both correct and attempted, or clear both." };
  }
  if (!WHOLE_NUMBER.test(correct) || !WHOLE_NUMBER.test(attempted)) {
    return { kind: "invalid", message: "Use whole numbers." };
  }
  const c = Number(correct);
  const a = Number(attempted);
  if (a < 1) return { kind: "invalid", message: "Attempted must be at least 1." };
  if (c > a) return { kind: "invalid", message: "Correct cannot be more than attempted." };
  return { kind: "valid", correct: c, attempted: a };
}

/** Totals over valid cells only; empty and invalid cells add nothing. */
export function sumCells(states: CellState[]): { correct: number; attempted: number } {
  let correct = 0;
  let attempted = 0;
  for (const state of states) {
    if (state.kind === "valid") {
      correct += state.correct;
      attempted += state.attempted;
    }
  }
  return { correct, attempted };
}

/** "—" when nothing was attempted (no data), otherwise a whole-number percentage. */
export function accuracyText(correct: number, attempted: number): string {
  return attempted <= 0 ? "—" : `${Math.round((correct / attempted) * 100)}%`;
}

/** Display hint only. No data (0) is "no data", not "limited". */
export function limitedResponses(attempted: number): boolean {
  return attempted > 0 && attempted < LIMITED_RESPONSE_THRESHOLD;
}

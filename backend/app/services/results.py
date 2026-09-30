"""Pure arithmetic and validation for section results. No database access."""

from dataclasses import dataclass

LIMITED_RESPONSE_THRESHOLD = 10


def accuracy(correct: int, attempted: int) -> float | None:
    """correct / attempted, or None when there is no data. No data is never reported as 0."""
    return None if attempted <= 0 else correct / attempted


def limited_responses(attempted: int) -> bool:
    """Display hint for small totals. No data (0 attempted) is 'no data', not 'limited'."""
    return 0 < attempted < LIMITED_RESPONSE_THRESHOLD


@dataclass(frozen=True)
class ResultRow:
    section_id: int
    item_id: int
    correct: int | None
    attempted: int | None


class ResultsError(ValueError):
    """The message is safe to show to the teacher."""


def plan_result_changes(
    rows: list[ResultRow], valid_section_ids: set[int], valid_item_ids: set[int]
) -> tuple[list[tuple[int, int, int, int]], list[tuple[int, int]]]:
    """Validate a whole batch before anything is written.

    Returns (upserts, clears). Upserts are (section_id, item_id, correct, attempted); clears are
    (section_id, item_id). Raises ResultsError on the first problem; the caller writes nothing.
    """
    seen: set[tuple[int, int]] = set()
    upserts: list[tuple[int, int, int, int]] = []
    clears: list[tuple[int, int]] = []
    for number, row in enumerate(rows, start=1):
        where = f"Row {number}"
        if row.section_id not in valid_section_ids:
            raise ResultsError(f"{where}: section {row.section_id} does not belong to this administration")
        if row.item_id not in valid_item_ids:
            raise ResultsError(f"{where}: question {row.item_id} does not belong to this administration")
        key = (row.section_id, row.item_id)
        if key in seen:
            raise ResultsError(f"{where}: duplicate entry for the same section and question")
        seen.add(key)
        if row.correct is None and row.attempted is None:
            clears.append(key)
            continue
        if row.correct is None or row.attempted is None:
            raise ResultsError(f"{where}: enter both correct and attempted, or clear both")
        if row.attempted < 1:
            raise ResultsError(f"{where}: attempted must be at least 1")
        if not 0 <= row.correct <= row.attempted:
            raise ResultsError(f"{where}: correct must be between 0 and attempted")
        upserts.append((row.section_id, row.item_id, row.correct, row.attempted))
    return upserts, clears

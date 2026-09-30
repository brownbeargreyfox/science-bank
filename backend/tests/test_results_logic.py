"""Pure rules for results: accuracy, the limited-response hint, and batch validation."""

import pytest

from app.services.results import ResultRow, ResultsError, accuracy, limited_responses, plan_result_changes


def test_accuracy_is_computed_and_no_data_is_none_not_zero():
    assert accuracy(12, 30) == pytest.approx(0.4)
    assert accuracy(0, 30) == 0.0
    assert accuracy(0, 30) is not None
    assert accuracy(0, 0) is None


@pytest.mark.parametrize(("attempted", "expected"), [(0, False), (1, True), (9, True), (10, False), (30, False)])
def test_limited_responses_flips_between_9_and_10_and_ignores_no_data(attempted, expected):
    assert limited_responses(attempted) is expected


SECTIONS, ITEMS = {1, 2}, {10, 11}


def plan(*rows):
    return plan_result_changes([ResultRow(*r) for r in rows], SECTIONS, ITEMS)


def test_valid_rows_split_into_upserts_and_clears():
    upserts, clears = plan((1, 10, 5, 10), (2, 10, 0, 7), (1, 11, None, None))
    assert upserts == [(1, 10, 5, 10), (2, 10, 0, 7)]
    assert clears == [(1, 11)]


@pytest.mark.parametrize(
    ("row", "fragment"),
    [
        ((3, 10, 1, 2), "section 3"),
        ((1, 99, 1, 2), "question 99"),
        ((1, 10, 1, 0), "at least 1"),
        ((1, 10, 3, 2), "between 0 and attempted"),
        ((1, 10, -1, 2), "between 0 and attempted"),
        ((1, 10, None, 5), "both correct and attempted"),
        ((1, 10, 5, None), "both correct and attempted"),
    ],
)
def test_invalid_rows_are_rejected(row, fragment):
    with pytest.raises(ResultsError, match=fragment):
        plan(row)


def test_duplicate_section_item_rows_are_rejected():
    with pytest.raises(ResultsError, match="duplicate"):
        plan((1, 10, 1, 2), (1, 10, 2, 3))


def test_one_bad_row_rejects_the_whole_batch():
    with pytest.raises(ResultsError):
        plan((1, 10, 5, 10), (1, 11, 9, 2))

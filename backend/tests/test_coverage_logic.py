"""School-year scope rules for the coverage grid. Pure; no database."""

from datetime import date

import pytest

from app.services.coverage import (
    resolve_scope,
    school_year_for,
    school_year_label,
    school_year_range,
)


@pytest.mark.parametrize(
    ("d", "year"),
    [
        (date(2026, 7, 31), 2025),
        (date(2026, 8, 1), 2026),
        (date(2027, 1, 15), 2026),
        (date(2027, 7, 31), 2026),
        (date(2027, 8, 1), 2027),
        (date(2028, 2, 29), 2027),  # leap day belongs to the year that began the previous August
    ],
)
def test_school_year_for_splits_on_august_first(d, year):
    assert school_year_for(d) == year


def test_school_year_range_is_inclusive_aug_1_to_jul_31():
    assert school_year_range(2026) == (date(2026, 8, 1), date(2027, 7, 31))


def test_school_year_label_uses_two_digit_end_year():
    assert school_year_label(2026) == "2026-27 school year"
    assert school_year_label(2099) == "2099-00 school year"


def test_resolve_scope_defaults_to_the_current_school_year():
    s = resolve_scope(None, date(2027, 3, 1))
    assert (s.kind, s.year, s.label) == ("school_year", 2026, "2026-27 school year")
    assert (s.start, s.end) == (date(2026, 8, 1), date(2027, 7, 31))
    assert resolve_scope(None, date(2027, 8, 1)).year == 2027


def test_resolve_scope_all_is_explicit_and_unbounded():
    s = resolve_scope("all", date(2027, 3, 1))
    assert (s.kind, s.year, s.label, s.start, s.end) == ("all_time", None, "All time", None, None)


def test_resolve_scope_accepts_a_school_year_start():
    s = resolve_scope("2024", date(2027, 3, 1))
    assert (s.year, s.start, s.end) == (2024, date(2024, 8, 1), date(2025, 7, 31))


@pytest.mark.parametrize("raw", ["abc", "", "ALL", "2026-27", "1999", "2101", "-5", "20.5"])
def test_resolve_scope_rejects_anything_else(raw):
    with pytest.raises(ValueError, match="year"):
        resolve_scope(raw, date(2027, 3, 1))

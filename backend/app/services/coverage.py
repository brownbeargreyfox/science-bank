"""Scope rules for the coverage grid: a school year runs Aug 1 to Jul 31, or all time. Pure; no database."""

from dataclasses import dataclass
from datetime import date

SCHOOL_YEAR_START_MONTH = 8
MIN_YEAR, MAX_YEAR = 2000, 2100


@dataclass(frozen=True)
class Scope:
    kind: str  # "school_year" | "all_time"
    year: int | None
    label: str
    start: date | None
    end: date | None


def today() -> date:
    """The server's date. A function so tests can substitute a clock."""
    return date.today()


def school_year_for(d: date) -> int:
    """The calendar year in which the school year containing `d` began."""
    return d.year if d.month >= SCHOOL_YEAR_START_MONTH else d.year - 1


def school_year_range(year: int) -> tuple[date, date]:
    return date(year, SCHOOL_YEAR_START_MONTH, 1), date(year + 1, SCHOOL_YEAR_START_MONTH - 1, 31)


def school_year_label(year: int) -> str:
    return f"{year}-{(year + 1) % 100:02d} school year"


def resolve_scope(raw: str | None, current: date) -> Scope:
    """`None` is the current school year, `"all"` is every date, a four-digit year is that school year's start."""
    if raw is None:
        year = school_year_for(current)
    elif raw == "all":
        return Scope("all_time", None, "All time", None, None)
    elif raw.isascii() and raw.isdigit() and MIN_YEAR <= int(raw) <= MAX_YEAR:
        year = int(raw)
    else:
        raise ValueError(f'year must be "all" or a school-year start between {MIN_YEAR} and {MAX_YEAR}')
    start, end = school_year_range(year)
    return Scope("school_year", year, school_year_label(year), start, end)

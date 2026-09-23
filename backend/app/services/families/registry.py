from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, Standard
from app.models import QuestionFamily as QuestionFamilyRow
from app.services.engine.family import QuestionFamily
from app.services.families.genetics import TraitProbability
from app.services.families.population import PopulationCarryingCapacity
from app.services.families.reaction_rate import ReactionRate

FAMILIES: dict[str, QuestionFamily] = {
    f.key: f for f in (PopulationCarryingCapacity(), TraitProbability(), ReactionRate())
}


def get_family(key: str) -> QuestionFamily:
    return FAMILIES[key]


def families_for_standard(standard: Standard) -> list[QuestionFamily]:
    course = standard.course
    return [
        f
        for f in FAMILIES.values()
        if any(
            b.state == course.state and b.course_slug == course.slug and b.code == standard.code for b in f.bindings
        )
    ]


def validate_family_citations(db: Session, family: QuestionFamily) -> list[str]:
    """Every template must cite an observable-performance bullet that exists for every bound standard."""
    problems = []
    for b in family.bindings:
        standards = db.scalars(
            select(Standard)
            .join(Course)
            .where(Course.state == b.state, Course.slug == b.course_slug, Standard.code == b.code)
        ).all()
        if not standards:
            problems.append(f"{family.key}: bound standard {b} not found")
        for std in standards:
            for t in family.templates:
                bullets = std.observable_performances.get(t.observable_category) or []
                if t.observable_index >= len(bullets):
                    problems.append(
                        f"{family.key}/{t.key}: {std.code} ({std.course.use_year}) has no observable "
                        f"{t.observable_category}[{t.observable_index}]"
                    )
    return problems


def sync_families(db: Session) -> int:
    for family in FAMILIES.values():
        problems = validate_family_citations(db, family)
        if problems:
            raise RuntimeError("; ".join(problems))
        catalog = family.catalog()
        row = db.get(QuestionFamilyRow, family.key)
        if row is None:
            row = QuestionFamilyRow(key=family.key)
            db.add(row)
        row.version = family.version
        row.title = family.title
        row.description = family.description
        row.bindings = catalog["bindings"]
        row.templates = catalog["templates"]
    db.flush()
    return len(FAMILIES)

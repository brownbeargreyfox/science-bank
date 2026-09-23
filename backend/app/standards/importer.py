"""Idempotent loader for data/standards/<STATE>/<use_year>/*.json into Postgres.

The JSON files are the system of record and are only ever read. Rows are keyed on natural keys
(state + use_year + course slug, course + PE code, course + bundle name), so re-running the import
is a no-op unless the source data changed. Standards are never deleted: generated questions keep
pointing at the exact row they were built against.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Bundle, BundleStandard, Course, SourceDocument, Standard, Topic

REQUIRED_STANDARD_KEYS = (
    "code",
    "performance_expectation",
    "sep",
    "dci",
    "ccc",
    "observable_performances",
)


class StandardsDataError(ValueError):
    pass


@dataclass
class ImportReport:
    created: dict[str, int] = field(default_factory=dict)
    updated: dict[str, int] = field(default_factory=dict)
    unchanged: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def bump(self, bucket: str, kind: str) -> None:
        counter = getattr(self, bucket)
        counter[kind] = counter.get(kind, 0) + 1

    def summary(self) -> str:
        kinds = sorted(set(self.created) | set(self.updated) | set(self.unchanged))
        lines = [
            f"{k}: {self.created.get(k, 0)} created, {self.updated.get(k, 0)} updated, "
            f"{self.unchanged.get(k, 0)} unchanged"
            for k in kinds
        ]
        return "\n".join(lines + [f"WARNING: {w}" for w in self.warnings])


def _sha(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _find_source_entry(manifest: dict, filename: str, use_year: str) -> dict | None:
    for doc in manifest.get("documents", []):
        if doc.get("ingested_into") == filename and doc.get("use_year") in (None, use_year):
            return doc
    return None


def _upsert_source_document(
    db: Session, report: ImportReport, state: str, use_year: str, path: Path, data: dict, manifest: dict
) -> SourceDocument:
    entry = _find_source_entry(manifest, path.name, use_year) or {}
    key = f"{use_year}/{entry.get('id') or path.stem}"
    values = {
        "title": data.get("source_document") or entry.get("resource_type") or path.stem,
        "resource_type": entry.get("resource_type") or "Unknown",
        "authority": data.get("source_authority") or manifest.get("authority"),
        "use_year": use_year,
        "published": data.get("source_published") or entry.get("published"),
        "url": data.get("source_url") or manifest.get("standards_base_url"),
        "data_file": f"{state}/{use_year}/{path.name}",
        "content_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    doc = db.scalar(select(SourceDocument).where(SourceDocument.state == state, SourceDocument.document_key == key))
    if doc is None:
        doc = SourceDocument(state=state, document_key=key, **values)
        db.add(doc)
        report.bump("created", "source_documents")
    elif any(getattr(doc, k) != v for k, v in values.items()):
        for k, v in values.items():
            setattr(doc, k, v)
        report.bump("updated", "source_documents")
    else:
        report.bump("unchanged", "source_documents")
    db.flush()
    return doc


def _get_topic(db: Session, cache: dict[str, Topic], name: str) -> Topic:
    if name not in cache:
        topic = db.scalar(select(Topic).where(Topic.name == name))
        if topic is None:
            topic = Topic(name=name)
            db.add(topic)
            db.flush()
        cache[name] = topic
    return cache[name]


def _import_course_file(
    db: Session, report: ImportReport, state: str, use_year: str, path: Path, manifest: dict, topics: dict
) -> Course:
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("course", "domains"):
        if key not in data:
            raise StandardsDataError(f"{path}: missing top-level '{key}'")
    if data.get("use_year") and data["use_year"] != use_year:
        raise StandardsDataError(f"{path}: use_year {data['use_year']!r} does not match folder {use_year!r}")

    source = _upsert_source_document(db, report, state, use_year, path, data, manifest)
    slug = path.stem
    course_values = {
        "name": data["course"],
        "standards_base": data.get("standards_base"),
        "notes": data.get("notes"),
        "source_document_id": source.id,
    }
    course = db.scalar(
        select(Course).where(Course.state == state, Course.use_year == use_year, Course.slug == slug)
    )
    if course is None:
        course = Course(state=state, use_year=use_year, slug=slug, active=True, **course_values)
        db.add(course)
        db.flush()
        report.bump("created", "courses")
    elif any(getattr(course, k) != v for k, v in course_values.items()):
        for k, v in course_values.items():
            setattr(course, k, v)
        report.bump("updated", "courses")
    else:
        report.bump("unchanged", "courses")

    existing = {s.code: s for s in db.scalars(select(Standard).where(Standard.course_id == course.id))}
    seen: set[str] = set()
    order = 0
    for domain in data["domains"]:
        for raw in domain["standards"]:
            missing = [k for k in REQUIRED_STANDARD_KEYS if not raw.get(k)]
            if missing:
                raise StandardsDataError(f"{path}: {raw.get('code', '?')} missing {missing}")
            code = raw["code"]
            if code in seen:
                raise StandardsDataError(f"{path}: duplicate PE code {code}")
            seen.add(code)
            order += 1
            record = {"domain_code": domain["domain_code"], "domain_name": domain["domain_name"], **raw}
            digest = _sha(record)
            values = {
                "sort_order": order,
                "domain_code": domain["domain_code"],
                "domain_name": domain["domain_name"],
                "performance_expectation": raw["performance_expectation"],
                "clarification_statement": raw.get("clarification_statement"),
                "state_assessment_boundary": raw.get("state_assessment_boundary"),
                "sep": raw["sep"],
                "dci": raw["dci"],
                "ccc": raw["ccc"],
                "observable_performances": raw["observable_performances"],
                "terminology": raw.get("terminology") or [],
                "question_sentence_stems": raw.get("question_sentence_stems"),
                "question_family_candidate": bool(raw.get("question_family_candidate")),
                "repeat_of_biology_1": bool(raw.get("repeat_of_biology_1")),
                "content_sha256": digest,
            }
            standard = existing.get(code)
            if standard is None:
                standard = Standard(course_id=course.id, code=code, **values)
                db.add(standard)
                report.bump("created", "standards")
            elif standard.content_sha256 != digest or standard.sort_order != order:
                for k, v in values.items():
                    setattr(standard, k, v)
                report.bump("updated", "standards")
            else:
                report.bump("unchanged", "standards")
                continue
            standard.topics = [_get_topic(db, topics, t) for t in dict.fromkeys(raw.get("topics") or [])]
            db.flush()

    for code in sorted(set(existing) - seen):
        report.warnings.append(
            f"{course.name} {use_year}: {code} is in the database but no longer in {path.name}; kept for provenance"
        )
    return course


def _import_bundle_file(
    db: Session, report: ImportReport, state: str, use_year: str, path: Path, course: Course, manifest: dict
) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "bundles" not in data:
        raise StandardsDataError(f"{path}: missing 'bundles'")
    source = _upsert_source_document(db, report, state, use_year, path, data, manifest)
    by_code = {s.code: s for s in db.scalars(select(Standard).where(Standard.course_id == course.id))}
    existing = {b.name: b for b in db.scalars(select(Bundle).where(Bundle.course_id == course.id))}

    for order, raw in enumerate(data["bundles"], start=1):
        name = raw["name"]
        unresolved = [pe["code"] for pe in raw.get("aligned_pes", []) if pe["code"] not in by_code]
        if unresolved:
            raise StandardsDataError(f"{path}: bundle {name!r} aligns to unknown {course.name} PEs {unresolved}")
        digest = _sha(raw)
        bundle = existing.get(name)
        values = {
            "source_document_id": source.id,
            "sort_order": order,
            "narrative": raw.get("narrative", ""),
            "connected_pes": raw.get("connected_pes") or [],
            "example_anchoring_phenomena": raw.get("example_anchoring_phenomena") or [],
            "content_sha256": digest,
        }
        if bundle is None:
            bundle = Bundle(course_id=course.id, name=name, **values)
            db.add(bundle)
            report.bump("created", "bundles")
        elif bundle.content_sha256 != digest or bundle.sort_order != order:
            for k, v in values.items():
                setattr(bundle, k, v)
            bundle.aligned.clear()
            db.flush()
            report.bump("updated", "bundles")
        else:
            report.bump("unchanged", "bundles")
            continue
        bundle.aligned = [
            BundleStandard(standard_id=by_code[pe["code"]].id, position=i, partial=bool(pe.get("partial")))
            for i, pe in enumerate(raw.get("aligned_pes", []))
        ]
        db.flush()


def import_standards(db: Session, standards_dir: Path) -> ImportReport:
    report = ImportReport()
    if not standards_dir.is_dir():
        raise StandardsDataError(f"standards directory not found: {standards_dir}")
    topics: dict[str, Topic] = {}
    for state_dir in sorted(p for p in standards_dir.iterdir() if p.is_dir()):
        state = state_dir.name
        manifest_path = state_dir / "sources.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        for year_dir in sorted(p for p in state_dir.iterdir() if p.is_dir()):
            use_year = year_dir.name
            course_files = sorted(p for p in year_dir.glob("*.json") if not p.stem.endswith("-bundles"))
            courses = {
                p.stem: _import_course_file(db, report, state, use_year, p, manifest, topics) for p in course_files
            }
            for bundle_path in sorted(year_dir.glob("*-bundles.json")):
                slug = bundle_path.stem.removesuffix("-bundles")
                if slug not in courses:
                    raise StandardsDataError(f"{bundle_path}: no matching course file {slug}.json")
                _import_bundle_file(db, report, state, use_year, bundle_path, courses[slug], manifest)
    db.flush()
    return report

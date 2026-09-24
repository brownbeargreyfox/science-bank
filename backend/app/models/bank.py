from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.standards import Course, Standard

ROLES = ("admin", "power", "regular")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role in ('admin', 'power', 'regular')", name="ck_users_role"),
        Index("uq_users_username_lower", text("lower(username)"), unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16), default="regular", server_default="regular")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class QuestionFamily(Base):
    """Catalog mirror of the code-defined deterministic generators (synced at startup)."""

    __tablename__ = "question_families"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    bindings: Mapped[list] = mapped_column(JSONB)
    templates: Mapped[list] = mapped_column(JSONB)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class GenerationRun(Base):
    """A saved generation: family + seed + options fully determine the output."""

    __tablename__ = "question_family_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    family_key: Mapped[str] = mapped_column(ForeignKey("question_families.key"))
    family_version: Mapped[str] = mapped_column(String(16))
    standard_id: Mapped[int] = mapped_column(ForeignKey("standards.id"))
    seed: Mapped[str] = mapped_column(String(64))
    options: Mapped[dict] = mapped_column(JSONB)
    parameters: Mapped[dict] = mapped_column(JSONB)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    standard: Mapped[Standard] = relationship()


class Stimulus(Base):
    __tablename__ = "stimuli"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("question_family_runs.id"))
    kind: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    standard_id: Mapped[int] = mapped_column(ForeignKey("standards.id"), index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("question_family_runs.id"))
    stimulus_id: Mapped[int | None] = mapped_column(ForeignKey("stimuli.id"))
    family_key: Mapped[str | None] = mapped_column(String(64), index=True)
    template_key: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), index=True, default="generated")
    provenance: Mapped[dict] = mapped_column(JSONB)
    current_version_no: Mapped[int] = mapped_column(Integer, default=1)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    standard: Mapped[Standard] = relationship()
    owner: Mapped[User] = relationship()
    stimulus: Mapped[Stimulus | None] = relationship()
    versions: Mapped[list["QuestionVersion"]] = relationship(
        back_populates="question", order_by="QuestionVersion.version_no", cascade="all, delete-orphan"
    )
    status_events: Mapped[list["QuestionStatusEvent"]] = relationship(
        order_by="QuestionStatusEvent.id", cascade="all, delete-orphan"
    )

    @property
    def current_version(self) -> "QuestionVersion":
        return next(v for v in self.versions if v.version_no == self.current_version_no)


class QuestionVersion(Base):
    """Immutable snapshot. Editing a question appends a new version; nothing is overwritten."""

    __tablename__ = "question_versions"
    __table_args__ = (UniqueConstraint("question_id", "version_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    version_no: Mapped[int] = mapped_column(Integer)
    origin: Mapped[str] = mapped_column(String(16))  # "engine" | "teacher_edit"
    question_type: Mapped[str] = mapped_column(String(32))  # "multiple_choice" | "constructed_response"
    dok: Mapped[int] = mapped_column(Integer)
    stem: Mapped[str] = mapped_column(Text)
    choices: Mapped[list] = mapped_column(JSONB, default=list)
    answer: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text, default="")
    change_note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    question: Mapped[Question] = relationship(back_populates="versions")


class QuestionStatusEvent(Base):
    __tablename__ = "question_status_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16))
    note: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"))
    instructions: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    course: Mapped[Course | None] = relationship()
    owner: Mapped[User] = relationship()
    items: Mapped[list["AssessmentItem"]] = relationship(
        back_populates="assessment", order_by="AssessmentItem.position", cascade="all, delete-orphan"
    )


class AssessmentItem(Base):
    """Pins a specific question version so later edits don't silently change a built assessment."""

    __tablename__ = "assessment_items"
    __table_args__ = (UniqueConstraint("assessment_id", "question_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    question_version_id: Mapped[int] = mapped_column(ForeignKey("question_versions.id"))
    position: Mapped[int] = mapped_column(Integer)

    assessment: Mapped[Assessment] = relationship(back_populates="items")
    question: Mapped[Question] = relationship()
    question_version: Mapped[QuestionVersion] = relationship()


class AuditEvent(Base):
    """Append-only record of security-relevant and content-changing actions."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    actor_username: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    target_type: Mapped[str | None] = mapped_column(Text)
    target_id: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))


class SiteSettings(Base):
    """Single row (id=1) of runtime-editable settings; seeded from env by migration 0003."""

    __tablename__ = "site_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_site_settings_singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    registration_open: Mapped[bool] = mapped_column(Boolean)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

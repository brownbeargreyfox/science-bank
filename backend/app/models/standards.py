from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class SourceDocument(Base):
    """One official SCDE source file as ingested (mirrors an entry in sources.json)."""

    __tablename__ = "source_documents"
    __table_args__ = (UniqueConstraint("state", "document_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    state: Mapped[str] = mapped_column(String(8))
    document_key: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(Text)
    resource_type: Mapped[str] = mapped_column(String(128))
    authority: Mapped[str | None] = mapped_column(Text)
    use_year: Mapped[str | None] = mapped_column(String(16))
    published: Mapped[str | None] = mapped_column(String(16))
    url: Mapped[str | None] = mapped_column(Text)
    data_file: Mapped[str | None] = mapped_column(Text)
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("state", "use_year", "slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    state: Mapped[str] = mapped_column(String(8))
    use_year: Mapped[str] = mapped_column(String(16))
    slug: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    standards_base: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"))

    source_document: Mapped[SourceDocument] = relationship()
    standards: Mapped[list["Standard"]] = relationship(back_populates="course", order_by="Standard.sort_order")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)


class StandardTopic(Base):
    __tablename__ = "standard_topics"

    standard_id: Mapped[int] = mapped_column(ForeignKey("standards.id", ondelete="CASCADE"), primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)


class Standard(Base):
    """A Performance Expectation within one course and one standards year."""

    __tablename__ = "standards"
    __table_args__ = (UniqueConstraint("course_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    code: Mapped[str] = mapped_column(String(32), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    domain_code: Mapped[str] = mapped_column(String(16))
    domain_name: Mapped[str] = mapped_column(Text)
    performance_expectation: Mapped[str] = mapped_column(Text)
    clarification_statement: Mapped[str | None] = mapped_column(Text)
    state_assessment_boundary: Mapped[str | None] = mapped_column(Text)
    sep: Mapped[dict] = mapped_column(JSONB)
    dci: Mapped[list] = mapped_column(JSONB)
    ccc: Mapped[dict] = mapped_column(JSONB)
    observable_performances: Mapped[dict] = mapped_column(JSONB)
    terminology: Mapped[list] = mapped_column(JSONB, default=list)
    question_sentence_stems: Mapped[list | None] = mapped_column(JSONB)
    question_family_candidate: Mapped[bool] = mapped_column(Boolean, default=False)
    repeat_of_biology_1: Mapped[bool] = mapped_column(Boolean, default=False)
    content_sha256: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    course: Mapped[Course] = relationship(back_populates="standards")
    topics: Mapped[list[Topic]] = relationship(secondary="standard_topics", order_by="Topic.name")


class Bundle(Base):
    __tablename__ = "bundles"
    __table_args__ = (UniqueConstraint("course_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(Text)
    narrative: Mapped[str] = mapped_column(Text)
    connected_pes: Mapped[list] = mapped_column(JSONB, default=list)
    example_anchoring_phenomena: Mapped[list] = mapped_column(JSONB, default=list)
    content_sha256: Mapped[str] = mapped_column(String(64))

    course: Mapped[Course] = relationship()
    source_document: Mapped[SourceDocument] = relationship()
    aligned: Mapped[list["BundleStandard"]] = relationship(
        back_populates="bundle", cascade="all, delete-orphan", order_by="BundleStandard.position"
    )


class BundleStandard(Base):
    __tablename__ = "bundle_standards"

    bundle_id: Mapped[int] = mapped_column(ForeignKey("bundles.id", ondelete="CASCADE"), primary_key=True)
    standard_id: Mapped[int] = mapped_column(ForeignKey("standards.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    partial: Mapped[bool] = mapped_column(Boolean, default=False)

    bundle: Mapped[Bundle] = relationship(back_populates="aligned")
    standard: Mapped[Standard] = relationship()

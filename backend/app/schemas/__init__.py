from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

QuestionStatus = Literal["generated", "reviewed", "approved", "rejected", "archived"]
Role = Literal["admin", "power", "regular"]
QuestionType = Literal["multiple_choice", "constructed_response"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- standards ------------------------------------------------------------------------------


class SourceDocumentOut(ORM):
    id: int
    state: str
    document_key: str
    title: str
    resource_type: str
    authority: str | None
    use_year: str | None
    published: str | None
    url: str | None
    data_file: str | None
    content_sha256: str | None
    imported_at: datetime


class CourseOut(ORM):
    id: int
    state: str
    use_year: str
    slug: str
    name: str
    standards_base: str | None
    notes: str | None
    active: bool
    standards_count: int
    bundles_count: int
    source_document: SourceDocumentOut


class FamilyRef(BaseModel):
    key: str
    title: str
    version: str


class StandardSummary(ORM):
    id: int
    course_id: int
    course_name: str
    course_slug: str
    use_year: str
    code: str
    domain_code: str
    domain_name: str
    performance_expectation: str
    topics: list[str]
    question_family_candidate: bool
    repeat_of_biology_1: bool
    families: list[FamilyRef]


class NamedText(BaseModel):
    name: str
    description: str


class DciOut(BaseModel):
    code: str
    name: str
    text: str


class BundleRef(BaseModel):
    id: int
    name: str
    partial: bool


class StandardDetail(StandardSummary):
    clarification_statement: str | None
    state_assessment_boundary: str | None
    sep: NamedText
    dci: list[DciOut]
    ccc: NamedText
    observable_performances: dict[str, list[str]]
    terminology: list[str]
    question_sentence_stems: list[str] | None
    content_sha256: str
    source_document: SourceDocumentOut
    bundles: list[BundleRef]
    question_counts: dict[str, int]


class BundleStandardOut(BaseModel):
    standard_id: int
    code: str
    partial: bool
    performance_expectation: str


class BundleOut(BaseModel):
    id: int
    course_id: int
    course_name: str
    name: str
    narrative: str
    aligned: list[BundleStandardOut]
    connected_pes: list[str]
    example_anchoring_phenomena: list[str]
    source_document_title: str


# ---- families and generation ---------------------------------------------------------------


class TemplateOut(BaseModel):
    key: str
    title: str
    dok: int
    question_type: QuestionType
    observable_category: str
    observable_index: int
    observable_text: str | None = None


class FamilyBindingOut(BaseModel):
    state: str
    course_slug: str
    code: str
    standard_ids: list[int]


class FamilyOut(BaseModel):
    key: str
    version: str
    title: str
    description: str
    stimulus_kind: str
    bindings: list[FamilyBindingOut]
    templates: list[TemplateOut]


class GenerateRequest(BaseModel):
    standard_id: int
    family_key: str
    seed: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9._-]*$")
    quantity: int = Field(default=5, ge=1, le=40)
    doks: list[int] = []
    question_types: list[QuestionType] = []
    template_keys: list[str] = []
    generation_mode: Literal["classroom", "eocep"] = "classroom"


class ChoiceOut(BaseModel):
    label: str
    text: str
    correct: bool
    rationale: str


class ObservableRef(BaseModel):
    category: str
    index: int
    text: str | None = None


class GeneratedQuestionOut(BaseModel):
    template_key: str
    title: str
    dok: int
    question_type: QuestionType
    stem: str
    choices: list[ChoiceOut]
    answer: str
    explanation: str
    observable: ObservableRef
    attempt: int


class GeneratedGroupOut(BaseModel):
    index: int
    parameters: dict[str, Any]
    stimulus: dict[str, Any]
    questions: list[GeneratedQuestionOut]


class GeneratePreviewOut(BaseModel):
    family_key: str
    family_version: str
    seed: str
    options: dict[str, Any]
    standard: StandardSummary
    groups: list[GeneratedGroupOut]


class GenerateSaveOut(BaseModel):
    run_id: int
    seed: str
    question_ids: list[int]


# ---- question bank --------------------------------------------------------------------------


class QuestionVersionOut(ORM):
    id: int
    version_no: int
    origin: Literal["engine", "teacher_edit"]
    question_type: QuestionType
    dok: int
    stem: str
    choices: list[ChoiceOut]
    answer: str
    explanation: str
    change_note: str | None
    created_at: datetime


class StimulusOut(ORM):
    id: int
    kind: str
    title: str
    body: dict[str, Any]


class StatusEventOut(ORM):
    id: int
    from_status: str | None
    to_status: str
    note: str | None
    created_at: datetime


class OwnerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class QuestionSummary(BaseModel):
    id: int
    status: QuestionStatus
    standard_id: int
    standard_code: str
    course_name: str
    use_year: str
    family_key: str | None
    template_key: str | None
    stimulus_id: int | None
    stimulus_title: str | None
    current_version_no: int
    origin: Literal["engine", "teacher_edit"]
    question_type: QuestionType
    dok: int
    stem: str
    updated_at: datetime
    owner: OwnerOut
    can_modify: bool


class QuestionPage(BaseModel):
    items: list[QuestionSummary]
    total: int
    page: int
    page_size: int
    status_counts: dict[str, int]


class QuestionDetail(BaseModel):
    id: int
    status: QuestionStatus
    allowed_transitions: list[QuestionStatus]
    standard: StandardSummary
    family_key: str | None
    template_key: str | None
    provenance: dict[str, Any]
    stimulus: StimulusOut | None
    current: QuestionVersionOut
    versions: list[QuestionVersionOut]
    status_events: list[StatusEventOut]
    assessment_ids: list[int]
    created_at: datetime
    updated_at: datetime
    owner: OwnerOut
    can_modify: bool


class ChoiceIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    correct: bool
    rationale: str = Field(default="", max_length=2000)


class QuestionEdit(BaseModel):
    stem: str = Field(min_length=1, max_length=10000)
    dok: int = Field(ge=1, le=4)
    choices: list[ChoiceIn] = []
    answer: str | None = Field(default=None, max_length=10000)
    explanation: str = Field(default="", max_length=10000)
    change_note: str | None = Field(default=None, max_length=1000)


class StatusChange(BaseModel):
    to_status: QuestionStatus
    note: str | None = Field(default=None, max_length=1000)


class BulkStatusChange(StatusChange):
    question_ids: list[int] = Field(min_length=1, max_length=200)


class BulkStatusOut(BaseModel):
    updated: list[int]
    skipped: dict[int, str]


# ---- assessments ----------------------------------------------------------------------------


class AssessmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    course_id: int | None = None
    instructions: str = Field(default="", max_length=5000)


class AssessmentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    course_id: int | None = None
    instructions: str | None = Field(default=None, max_length=5000)


class AssessmentItemOut(BaseModel):
    id: int
    position: int
    question_id: int
    question_status: QuestionStatus
    pinned_version_no: int
    latest_version_no: int
    standard_code: str
    course_name: str
    stimulus_id: int | None
    stimulus_title: str | None
    dok: int
    question_type: QuestionType
    stem: str


class AssessmentSummary(BaseModel):
    id: int
    title: str
    course_id: int | None
    course_name: str | None
    instructions: str
    item_count: int
    updated_at: datetime


class AssessmentDetail(AssessmentSummary):
    items: list[AssessmentItemOut]
    dok_distribution: dict[str, int]
    standards_coverage: list[dict[str, Any]]
    question_type_counts: dict[str, int]


class AddItems(BaseModel):
    question_ids: list[int] = Field(min_length=1, max_length=200)


class AddItemsOut(BaseModel):
    added: list[int]
    skipped: dict[int, str]


class ReorderItems(BaseModel):
    item_ids: list[int]


class PrintChoice(BaseModel):
    label: str
    text: str
    correct: bool | None = None
    rationale: str | None = None


class PrintQuestion(BaseModel):
    number: int
    question_type: QuestionType
    dok: int
    standard_code: str
    stem: str
    choices: list[PrintChoice]
    answer: str | None = None
    explanation: str | None = None
    teacher_edited: bool | None = None


class PrintBlock(BaseModel):
    stimulus: dict[str, Any] | None
    stimulus_title: str | None
    questions: list[PrintQuestion]


class PrintOut(BaseModel):
    variant: Literal["teacher", "student"]
    title: str
    course_name: str | None
    instructions: str
    question_count: int
    blocks: list[PrintBlock]
    standards: list[dict[str, Any]] | None = None

import type { components } from "./schema";

type S = components["schemas"];

export type Course = S["CourseOut"];
export type SourceDocument = S["SourceDocumentOut"];
export type StandardSummary = S["StandardSummary"];
export type StandardDetail = S["StandardDetail"];
export type Bundle = S["BundleOut"];
export type Family = S["FamilyOut"];
export type Template = S["TemplateOut"];
export type GenerateRequest = S["GenerateRequest"];
export type GeneratePreview = S["GeneratePreviewOut"];
export type GeneratedGroup = S["GeneratedGroupOut"];
export type GeneratedQuestion = S["GeneratedQuestionOut"];
export type GenerateSaveOut = S["GenerateSaveOut"];
export type QuestionSummary = S["QuestionSummary"];
export type QuestionPage = S["QuestionPage"];
export type QuestionDetail = S["QuestionDetail"];
export type QuestionVersion = S["QuestionVersionOut"];
export type QuestionEdit = S["QuestionEdit"];
export type Choice = S["ChoiceOut"];
export type ChoiceIn = S["ChoiceIn"];
export type Status = S["QuestionSummary"]["status"];
export type QuestionType = S["QuestionSummary"]["question_type"];
export type AssessmentSummary = S["AssessmentSummary"];
export type AssessmentDetail = S["AssessmentDetail"];
export type AssessmentItem = S["AssessmentItemOut"];
export type AddItemsOut = S["AddItemsOut"];
export type PrintOut = S["PrintOut"];
export type PrintBlock = S["PrintBlock"];
export type PrintQuestion = S["PrintQuestion"];
export type ObservableRef = S["ObservableRef"];
export type Role = S["SessionUser"]["role"];
export type AdminUser = S["AdminUserOut"];

export const STATUSES: readonly Status[] = ["generated", "reviewed", "approved", "rejected", "archived"];

export const STATUS_LABEL: Record<Status, string> = {
  generated: "Generated",
  reviewed: "Reviewed",
  approved: "Approved",
  rejected: "Rejected",
  archived: "Archived",
};

export const ROLES: readonly Role[] = ["admin", "power", "regular"];

export const ROLE_LABEL: Record<Role, string> = {
  admin: "Admin",
  power: "Power user",
  regular: "Teacher",
};

export const TYPE_LABEL: Record<QuestionType, string> = {
  multiple_choice: "Multiple choice",
  constructed_response: "Constructed response",
};

/*
 * The schema types the following payloads as bare `object`. These describe
 * what the backend actually sends; every reader parses defensively.
 */

export interface StimulusColumn {
  key: string;
  label: string;
}
export interface StimulusTable {
  caption: string;
  columns: StimulusColumn[];
  rows: Record<string, unknown>[];
}
export interface StimulusChart {
  type: "line" | "bar";
  title: string;
  x: { key: string; label: string };
  y: { label: string; min?: number | null; max?: number | null };
  series: { key: string; label: string }[];
  table_index: number;
}
export interface StimulusSection {
  heading: string;
  text: string;
  table_index?: number | null;
}
export interface StimulusBody {
  kind: string;
  title: string;
  intro: string;
  sections: StimulusSection[];
  tables: StimulusTable[];
  charts: StimulusChart[];
}

/** Snapshot stored with each generated question (QuestionDetail.provenance). */
export interface Provenance {
  seed?: string;
  attempt?: number;
  group_index?: number;
  generated_at?: string;
  family?: { key?: string; title?: string; version?: string };
  template?: { key?: string; title?: string; dok?: number };
  options?: { doks?: number[]; quantity?: number; template_keys?: string[]; question_types?: string[] };
  standard?: {
    id?: number;
    code?: string;
    state?: string;
    course?: string;
    use_year?: string;
    content_sha256?: string;
    performance_expectation?: string;
    state_assessment_boundary?: string | null;
  };
  source_document?: {
    url?: string | null;
    title?: string;
    authority?: string | null;
    data_file?: string | null;
    published?: string | null;
    content_sha256?: string | null;
  };
  observable_performance?: { text?: string | null; index?: number; category?: string };
}

export interface CoverageRow {
  standard_id?: number;
  code: string;
  course?: string;
  count?: number;
  performance_expectation?: string;
}

export interface PrintStandard {
  code: string;
  course?: string;
  use_year?: string;
  performance_expectation?: string;
}

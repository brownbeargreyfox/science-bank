import type { ReactNode } from "react";
import { Link } from "react-router";
import { errorText } from "../api/client";
import { STATUS_LABEL, TYPE_LABEL, type QuestionType, type Status } from "../api/types";

export function PageHeader({ title, lead, actions }: { title: ReactNode; lead?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0 max-w-3xl">
        <h1 className="text-[1.75rem] font-bold tracking-tight sm:text-[2rem]">{title}</h1>
        {lead ? <div className="mt-1.5 text-muted">{lead}</div> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </header>
  );
}

/** Standard code, always paired with its course because codes repeat across courses. */
export function CodeTag({ code, course, to }: { code: string; course?: string | null; to?: string }) {
  const inner = (
    <>
      <span>{code}</span>
      {course ? <span className="course">{course}</span> : null}
    </>
  );
  if (to) {
    return (
      <Link to={to} className="code-tag hover:bg-petrol-soft">
        {inner}
      </Link>
    );
  }
  return <span className="code-tag">{inner}</span>;
}

const STATUS_STYLE: Record<Status, string> = {
  generated: "bg-[#e7ecef] text-[#34444b] border-[#b9c5ca]",
  reviewed: "bg-bound-soft text-bound border-[#e2c28c]",
  approved: "bg-ok-soft text-ok border-[#a7d1b4]",
  rejected: "bg-danger-soft text-danger border-[#e5aaa6]",
  archived: "bg-[#eeeeee] text-[#4d4d4d] border-[#c4c4c4]",
};

export function StatusBadge({ status }: { status: Status }) {
  return <span className={`badge ${STATUS_STYLE[status]}`}>{STATUS_LABEL[status]}</span>;
}

export function DokBadge({ dok }: { dok: number }) {
  return (
    <span className="badge border-line bg-surface text-ink" title={`Depth of Knowledge level ${dok}`}>
      DOK {dok}
    </span>
  );
}

export function TypeBadge({ type, short = false }: { type: QuestionType; short?: boolean }) {
  return (
    <span className="badge border-line bg-surface text-muted">
      {short ? (type === "multiple_choice" ? "MC" : "CR") : TYPE_LABEL[type]}
    </span>
  );
}

export function OriginBadge({ origin }: { origin: "engine" | "teacher_edit" }) {
  return origin === "engine" ? (
    <span className="badge border-petrol bg-petrol-soft text-petrol-dark">Engine-generated key</span>
  ) : (
    <span className="badge border-[#a37fc0] bg-[#f3ebf9] text-[#5a2d7f]">Teacher-edited</span>
  );
}

export function Pill({ children }: { children: ReactNode }) {
  return <span className="badge border-line-soft bg-paper font-normal text-muted">{children}</span>;
}

export function ErrorNotice({ error, title }: { error: unknown; title?: string }) {
  if (!error) return null;
  return (
    <div role="alert" className="rounded-md border border-[#e5aaa6] bg-danger-soft px-4 py-3 text-danger">
      {title ? <p className="font-bold">{title}</p> : null}
      <p>{errorText(error)}</p>
    </div>
  );
}

export function Notice({ children, tone = "ok" }: { children: ReactNode; tone?: "ok" | "info" | "warn" }) {
  const cls =
    tone === "ok"
      ? "border-[#a7d1b4] bg-ok-soft text-ok"
      : tone === "warn"
        ? "border-[#e2c28c] bg-bound-soft text-bound"
        : "border-line bg-petrol-soft text-petrol-dark";
  return <div className={`rounded-md border px-4 py-3 ${cls}`}>{children}</div>;
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <p role="status" className="py-6 text-muted">
      {label}
    </p>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-md border border-dashed border-line px-4 py-8 text-center text-muted">{children}</div>;
}

export function Section({
  title,
  children,
  actions,
  id,
  className = "",
}: {
  title: ReactNode;
  children: ReactNode;
  actions?: ReactNode;
  id?: string;
  className?: string;
}) {
  return (
    <section className={`panel p-4 sm:p-5 ${className}`} aria-labelledby={id}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 id={id} className="text-lg font-bold">
          {title}
        </h2>
        {actions}
      </div>
      {children}
    </section>
  );
}

/** Definition-list row used by provenance panels. */
export function Meta({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-0.5 border-b border-line-soft py-2 last:border-b-0">
      <dt className="text-sm font-bold text-muted">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}

export function Hash({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="text-muted">Not recorded</span>;
  return (
    <code className="block break-all text-[0.8125rem] text-muted" title={value}>
      {value}
    </code>
  );
}

export function FamilyBadge() {
  return <span className="badge border-petrol bg-petrol-soft text-petrol-dark">Question family available</span>;
}

export function RepeatBadge() {
  return <span className="badge border-line bg-paper text-muted">Repeat of Biology 1</span>;
}

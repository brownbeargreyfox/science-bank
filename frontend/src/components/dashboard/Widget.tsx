import type { ReactNode } from "react";

export function Widget({ id, title, actions, children, className = "" }: { id: string; title: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`panel min-w-0 p-4 sm:p-5 ${className}`} aria-labelledby={id}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2">
        <h2 id={id} className="text-[0.9375rem] font-bold">{title}</h2>
        {actions}
      </div>
      {children}
    </section>
  );
}

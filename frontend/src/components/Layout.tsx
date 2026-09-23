import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { api, unwrap } from "../api/client";
import { ME_KEY, queryClient, useMe } from "../api/queries";
import { ErrorNotice, Loading } from "./ui";

const NAV = [
  { to: "/", label: "Home", end: true },
  { to: "/standards", label: "Standards" },
  { to: "/bundles", label: "Bundles" },
  { to: "/generate", label: "Generate" },
  { to: "/questions", label: "Question bank" },
  { to: "/assessments", label: "Assessments" },
];

/** Gate for every signed-in route. A 401 anywhere flips `me` to null and lands here. */
export function RequireAuth() {
  const me = useMe();
  const location = useLocation();
  if (me.isPending) return <Loading label="Checking your session…" />;
  if (me.isError)
    return (
      <div className="mx-auto max-w-lg p-6">
        <ErrorNotice error={me.error} title="Science Bank could not reach the server." />
      </div>
    );
  if (!me.data) {
    const next = location.pathname + location.search;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }
  return <Outlet />;
}

function useLogout() {
  const navigate = useNavigate();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/auth/logout")),
    onSettled: () => {
      queryClient.clear();
      queryClient.setQueryData(ME_KEY, null);
      navigate("/login", { replace: true });
    },
  });
}

function Brand() {
  return (
    <span className="flex items-center gap-2.5">
      <svg width="30" height="30" viewBox="0 0 30 30" aria-hidden="true">
        <rect x="1" y="1" width="28" height="28" rx="4" fill="#0f5563" />
        <path d="M11 6h8M13 6v7l-5.5 9.5a1.6 1.6 0 0 0 1.4 2.5h12.2a1.6 1.6 0 0 0 1.4-2.5L17 13V6" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinejoin="round" />
        <path d="M9.6 19h10.8" stroke="#fbe38a" strokeWidth="2.4" />
      </svg>
      <span className="text-lg font-bold tracking-tight">Science Bank</span>
    </span>
  );
}

export function AppLayout() {
  const me = useMe();
  const logout = useLogout();
  const [open, setOpen] = useState(false);

  const nav = (
    <ul className="flex flex-col gap-0.5">
      {NAV.map((n) => (
        <li key={n.to}>
          <NavLink
            to={n.to}
            end={n.end}
            onClick={() => setOpen(false)}
            className={({ isActive }) =>
              `block rounded-md px-3 py-2 font-bold no-underline ${
                isActive
                  ? "bg-petrol text-white hover:text-white"
                  : "text-ink hover:bg-petrol-soft hover:text-petrol-dark"
              }`
            }
          >
            {n.label}
          </NavLink>
        </li>
      ))}
    </ul>
  );

  const account = (
    <div className="flex items-center justify-between gap-2 border-t border-line pt-3 text-sm">
      <span className="text-muted">
        Signed in as <strong className="text-ink">{me.data?.username}</strong>
      </span>
      <button type="button" className="btn btn-sm" onClick={() => logout.mutate()} disabled={logout.isPending}>
        Log out
      </button>
    </div>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[15rem_1fr]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      {/* Phone / tablet top bar */}
      <header className="no-print sticky top-0 z-30 border-b border-line bg-surface lg:hidden">
        <div className="flex items-center justify-between px-4 py-2.5">
          <NavLink to="/" className="text-ink no-underline">
            <Brand />
          </NavLink>
          <button
            type="button"
            className="btn btn-sm"
            aria-expanded={open}
            aria-controls="mobile-nav"
            onClick={() => setOpen((o) => !o)}
          >
            {open ? "Close menu" : "Menu"}
          </button>
        </div>
        {open ? (
          <nav id="mobile-nav" aria-label="Main" className="space-y-3 border-t border-line px-4 pt-2 pb-4">
            {nav}
            {account}
          </nav>
        ) : null}
      </header>

      {/* Desktop sidebar */}
      <aside className="no-print sticky top-0 hidden h-screen flex-col gap-6 border-r border-line bg-surface px-3 py-5 lg:flex">
        <NavLink to="/" className="px-2 text-ink no-underline">
          <Brand />
        </NavLink>
        <nav aria-label="Main" className="flex-1">
          {nav}
        </nav>
        <div className="px-1">{account}</div>
      </aside>

      <main id="main" tabIndex={-1} className="min-w-0 px-4 py-6 outline-none sm:px-6 lg:px-10 lg:py-8">
        <div className="mx-auto max-w-6xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

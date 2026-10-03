import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import {
  PanelLeftContract24Regular,
  PanelLeftExpand24Regular,
} from "@fluentui/react-icons";
import {
  Navigate,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
} from "react-router";
import { api, unwrap } from "../api/client";
import { ME_KEY, queryClient, useMe } from "../api/queries";
import { ROLE_LABEL } from "../api/types";
import { NAV_ICONS } from "./navIcons";
import { ErrorNotice, Loading } from "./ui";

const NAV = [
  { to: "/", label: "Overview", end: true },
  { to: "/standards", label: "Standards" },
  { to: "/bundles", label: "Bundles" },
  { to: "/coverage", label: "Coverage" },
  { to: "/generate", label: "Generate" },
  { to: "/questions", label: "Question bank" },
  { to: "/assessments", label: "Assessments" },
  { to: "/results", label: "Results" },
];
const ADMIN_NAV: (typeof NAV)[number] = {
  to: "/admin/users",
  label: "Admin",
  end: false,
};

/** Gate for every signed-in route. A 401 anywhere flips `me` to null and lands here. */
export function RequireAuth() {
  const me = useMe();
  const location = useLocation();
  if (me.isPending) return <Loading label="Checking your session…" />;
  if (me.isError)
    return (
      <div className="mx-auto max-w-lg p-6">
        <ErrorNotice
          error={me.error}
          title="Science Bank could not reach the server."
        />
      </div>
    );
  if (!me.data) {
    const next = location.pathname + location.search;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }
  return <Outlet />;
}

/** Hides admin pages from non-admins; the API enforces the same rule. */
export function RequireAdmin() {
  const me = useMe();
  if (me.data?.role !== "admin") return <Navigate to="/" replace />;
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
      <svg width="28" height="28" viewBox="0 0 30 30" aria-hidden="true">
        <rect x="1" y="1" width="28" height="28" rx="2" fill="#fff" />
        <path
          d="M11 6h8M13 6v7l-5.5 9.5a1.6 1.6 0 0 0 1.4 2.5h12.2a1.6 1.6 0 0 0 1.4-2.5L17 13V6"
          fill="none"
          stroke="#106ebe"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <path d="M9.6 19h10.8" stroke="#f2b400" strokeWidth="2.4" />
      </svg>
      <span className="whitespace-nowrap text-lg font-bold tracking-tight">
        Science Bank
      </span>
    </span>
  );
}

const PIN_KEY = "science-bank:rail-pinned";

/** Whether the rail is kept open. Remembered per browser; touch screens have no hover, so this is their way in. */
function usePinnedRail(): [boolean, () => void] {
  const [pinned, setPinned] = useState(() => {
    try {
      return window.localStorage.getItem(PIN_KEY) === "1";
    } catch {
      return false;
    }
  });
  const toggle = () =>
    setPinned((current) => {
      const next = !current;
      try {
        window.localStorage.setItem(PIN_KEY, next ? "1" : "0");
      } catch {
        // Storage can be blocked (private windows); the rail still works for this visit.
      }
      return next;
    });
  return [pinned, toggle];
}

function NavIcon({
  to,
  active,
  className,
}: {
  to: string;
  active: boolean;
  className?: string;
}) {
  const icons = NAV_ICONS[to];
  if (!icons) return null;
  const Icon = active ? icons.filled : icons.regular;
  return <Icon className={className} aria-hidden="true" />;
}

export function AppLayout() {
  const me = useMe();
  const logout = useLogout();
  const [open, setOpen] = useState(false);
  const [pinned, togglePinned] = usePinnedRail();
  const items = me.data?.role === "admin" ? [...NAV, ADMIN_NAV] : NAV;

  const account = (
    <span className="flex items-center gap-3 text-sm">
      {me.data ? (
        <span className="hidden text-right leading-tight sm:block">
          <span className="block font-bold">{me.data.username}</span>
          <span className="block text-xs opacity-90">
            {ROLE_LABEL[me.data.role]}
          </span>
        </span>
      ) : null}
      <button
        type="button"
        className="btn btn-sm"
        onClick={() => logout.mutate()}
        disabled={logout.isPending}
      >
        Log out
      </button>
    </span>
  );

  return (
    <div className="min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      <header className="topbar no-print sticky top-0 z-30 flex items-center gap-3 px-3 sm:px-4">
        <button
          type="button"
          className="btn btn-sm lg:hidden"
          aria-expanded={open}
          aria-controls="mobile-nav"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((o) => !o)}
        >
          {open ? "Close" : "Menu"}
        </button>
        <NavLink to="/" className="no-underline hover:text-white">
          <Brand />
        </NavLink>
        <div className="ml-auto">{account}</div>
      </header>

      {open ? (
        <nav
          id="mobile-nav"
          aria-label="Main"
          className="no-print border-b border-line bg-surface lg:hidden"
        >
          <ul>
            {items.map((n) => (
              <li key={n.to}>
                <NavLink
                  to={n.to}
                  end={n.end}
                  onClick={() => setOpen(false)}
                  className="rail-item"
                  style={{ height: "2.75rem" }}
                >
                  {({ isActive }) => (
                    <>
                      <NavIcon
                        to={n.to}
                        active={isActive}
                        className="rail-icon"
                      />
                      <span>{n.label}</span>
                    </>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}

      <nav
        aria-label="Main"
        className="rail no-print hidden lg:flex lg:flex-col"
        data-pinned={pinned}
      >
        <ul className="flex-1 pt-1.5">
          {items.map((n) => (
            <li key={n.to}>
              <NavLink to={n.to} end={n.end} className="rail-item">
                {({ isActive }) => (
                  <>
                    <NavIcon
                      to={n.to}
                      active={isActive}
                      className="rail-icon"
                    />
                    <span className="rail-label">{n.label}</span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="rail-item w-full border-t border-line text-left"
          aria-pressed={pinned}
          onClick={togglePinned}
        >
          {pinned ? (
            <PanelLeftContract24Regular
              className="rail-icon"
              aria-hidden="true"
            />
          ) : (
            <PanelLeftExpand24Regular
              className="rail-icon"
              aria-hidden="true"
            />
          )}
          <span className="rail-label">
            {pinned ? "Unpin menu" : "Keep menu open"}
          </span>
        </button>
      </nav>

      <main
        id="main"
        tabIndex={-1}
        className={`min-w-0 px-4 py-6 outline-none sm:px-6 lg:py-8 ${
          pinned
            ? "lg:pl-[calc(var(--rail-expanded)+2.5rem)]"
            : "lg:pl-[calc(var(--rail-collapsed)+2.5rem)]"
        } lg:pr-10`}
      >
        <div className="mx-auto max-w-6xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router";
import { api, unwrap } from "../api/client";
import { ME_KEY, queryClient, useMe } from "../api/queries";
import { ErrorNotice } from "../components/ui";
import { safeNext } from "../lib/format";

export default function LoginPage() {
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const navigate = useNavigate();
  const me = useMe();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const registration = useQuery({
    queryKey: ["auth", "registration-status"],
    queryFn: () => unwrap(api.GET("/api/auth/registration-status")),
  });

  const login = useMutation({
    mutationFn: () => unwrap(api.POST("/api/auth/login", { body: { username, password } })),
    onSuccess: (user) => {
      queryClient.setQueryData(ME_KEY, user);
      navigate(next, { replace: true });
    },
  });

  const register = useMutation({
    mutationFn: () => unwrap(api.POST("/api/auth/register", { body: { username, password } })),
    onSuccess: (user) => {
      queryClient.setQueryData(ME_KEY, user);
      navigate(next, { replace: true });
    },
  });

  if (me.data) return <Navigate to={next} replace />;

  const canRegister = registration.data?.registration_open === true;
  const isRegistering = mode === "register" && canRegister;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    (isRegistering ? register : login).mutate();
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-3">
          <svg width="40" height="40" viewBox="0 0 30 30" aria-hidden="true">
            <rect x="1" y="1" width="28" height="28" rx="4" fill="#0f5563" />
            <path d="M11 6h8M13 6v7l-5.5 9.5a1.6 1.6 0 0 0 1.4 2.5h12.2a1.6 1.6 0 0 0 1.4-2.5L17 13V6" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinejoin="round" />
            <path d="M9.6 19h10.8" stroke="#fbe38a" strokeWidth="2.4" />
          </svg>
          <div>
            <h1 className="text-2xl font-bold">Science Bank</h1>
            <p className="text-sm text-muted">Question bank for SC Biology and Chemistry</p>
          </div>
        </div>
        <form onSubmit={submit} className="panel space-y-4 p-5" noValidate>
          <div className="flex rounded-lg bg-slate-100 p-1 text-sm font-medium" role="tablist" aria-label="Account action">
            <button type="button" role="tab" aria-selected={!isRegistering} className={`flex-1 rounded-md px-3 py-2 ${!isRegistering ? "bg-white text-ink shadow-sm" : "text-muted"}`} onClick={() => setMode("login")}>Log in</button>
            {canRegister ? <button type="button" role="tab" aria-selected={isRegistering} className={`flex-1 rounded-md px-3 py-2 ${isRegistering ? "bg-white text-ink shadow-sm" : "text-muted"}`} onClick={() => setMode("register")}>Create account</button> : null}
          </div>
          {isRegistering ? <p className="rounded border border-teal-200 bg-teal-50 p-3 text-sm text-teal-900">Create a teacher account for this private installation.</p> : null}
          <div>
            <label htmlFor="username" className="field-label">
              Username
            </label>
            <input
              id="username"
              className="input"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
            />
          </div>
          <div>
            <label htmlFor="password" className="field-label">
              Password
            </label>
            <input
              id="password"
              type="password"
              className="input"
              autoComplete={isRegistering ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <p className="text-xs text-muted">{isRegistering ? "Use at least 12 characters for the password." : null}</p>
          <div aria-live="polite">{login.isError ? <ErrorNotice error={login.error} /> : register.isError ? <ErrorNotice error={register.error} /> : null}</div>
          <button type="submit" className="btn btn-primary w-full" disabled={login.isPending || register.isPending || !username || !password || (isRegistering && password.length < 12)}>
            {isRegistering ? (register.isPending ? "Creating account…" : "Create teacher account") : login.isPending ? "Logging in…" : "Log in"}
          </button>
        </form>
      </div>
    </main>
  );
}

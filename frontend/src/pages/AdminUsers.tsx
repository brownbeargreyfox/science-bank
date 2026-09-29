import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, unwrap } from "../api/client";
import { ADMIN_USERS_KEY, SITE_SETTINGS_KEY, queryClient, useAdminUsers, useMe, useSiteSettings } from "../api/queries";
import { ROLE_LABEL, ROLES, type AdminUser, type Role } from "../api/types";
import { ErrorNotice, Loading, Notice, PageHeader, Section } from "../components/ui";
import { formatDate, formatDateTime } from "../lib/format";

const PASSWORD_MIN = 12;

/** Client-side check before sending; the server enforces the same rules. */
function passwordProblem(password: string, confirm: string): string | null {
  if (password.length < PASSWORD_MIN) return `Use at least ${PASSWORD_MIN} characters.`;
  if (password !== confirm) return "The two passwords don't match.";
  return null;
}

function invalidateUsers() {
  void queryClient.invalidateQueries({ queryKey: ADMIN_USERS_KEY });
}

function RegistrationCard() {
  const settings = useSiteSettings();
  const update = useMutation({
    mutationFn: (open: boolean) =>
      unwrap(api.PATCH("/api/admin/settings", { body: { registration_open: open } })),
    onSuccess: (data) => queryClient.setQueryData(SITE_SETTINGS_KEY, data),
  });
  return (
    <Section title="Registration" id="reg-h">
      <ErrorNotice error={settings.error ?? update.error} />
      {settings.isPending ? (
        <Loading />
      ) : (
        <label className="flex items-start gap-2">
          <input
            type="checkbox"
            className="mt-1"
            checked={settings.data?.registration_open ?? false}
            disabled={update.isPending}
            onChange={(e) => update.mutate(e.target.checked)}
          />
          <span>
            Allow new teachers to create their own accounts
            <span className="block text-sm text-muted">
              New self-registered accounts are regular teachers. You can change their role below.
            </span>
          </span>
        </label>
      )}
    </Section>
  );
}

function ResetPassword({ user, onDone }: { user: AdminUser; onDone: () => void }) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [touched, setTouched] = useState(false);
  const problem = passwordProblem(password, confirm);
  const reset = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/admin/users/{user_id}/password", { params: { path: { user_id: user.id } }, body: { password } })),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!problem) reset.mutate();
  };
  if (reset.isSuccess) {
    return (
      <div className="space-y-2">
        <Notice>Password updated for {user.username}. Their existing sessions stay signed in.</Notice>
        <button type="button" className="btn btn-sm" onClick={onDone}>
          Close
        </button>
      </div>
    );
  }
  return (
    <form onSubmit={submit} className="grid gap-2 sm:grid-cols-[1fr_1fr_auto_auto] sm:items-end">
      <div>
        <label htmlFor={`pw-${user.id}`} className="field-label">
          New password for {user.username}
        </label>
        <input
          id={`pw-${user.id}`}
          type="password"
          autoComplete="new-password"
          className="input"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      <div>
        <label htmlFor={`pw2-${user.id}`} className="field-label">
          Repeat it
        </label>
        <input
          id={`pw2-${user.id}`}
          type="password"
          autoComplete="new-password"
          className="input"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
      </div>
      <button type="submit" className="btn btn-primary" disabled={reset.isPending}>
        {reset.isPending ? "Saving…" : "Set password"}
      </button>
      <button type="button" className="btn btn-quiet" onClick={onDone}>
        Cancel
      </button>
      <div className="sm:col-span-4" aria-live="polite">
        {touched && problem ? <p className="text-danger">{problem}</p> : null}
        <ErrorNotice error={reset.error} />
      </div>
    </form>
  );
}

function UserRow({ user, isSelf }: { user: AdminUser; isSelf: boolean }) {
  const [resetting, setResetting] = useState(false);
  const update = useMutation({
    mutationFn: (body: { role?: Role; is_active?: boolean }) =>
      unwrap(api.PATCH("/api/admin/users/{user_id}", { params: { path: { user_id: user.id } }, body })),
    // Refetch on failure too, so a refused change (e.g. last admin) snaps the control back.
    onSettled: invalidateUsers,
  });
  const selfTitle = isSelf ? "Use another admin account or the CLI to change your own access" : undefined;
  return (
    <>
      <tr className={user.is_active ? undefined : "text-muted"}>
        <th scope="row">
          {user.username}
          {isSelf ? <span className="ml-1 text-sm font-normal text-muted">(you)</span> : null}
        </th>
        <td>
          <label className="sr-only" htmlFor={`role-${user.id}`}>
            Role for {user.username}
          </label>
          <select
            id={`role-${user.id}`}
            className="input w-auto min-w-32 py-1"
            value={user.role}
            disabled={isSelf || update.isPending}
            title={selfTitle}
            onChange={(e) => update.mutate({ role: e.target.value as Role })}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABEL[r]}
              </option>
            ))}
          </select>
        </td>
        <td>
          <label className="flex items-center gap-2" title={selfTitle}>
            <input
              type="checkbox"
              checked={user.is_active}
              disabled={isSelf || update.isPending}
              onChange={(e) => update.mutate({ is_active: e.target.checked })}
            />
            {user.is_active ? "Active" : "Disabled"}
          </label>
        </td>
        <td className="text-sm whitespace-nowrap" title={formatDateTime(user.last_login_at)}>
          {user.last_login_at ? formatDate(user.last_login_at) : "never"}
        </td>
        <td>
          <button type="button" className="btn btn-sm" onClick={() => setResetting((r) => !r)}>
            Reset password
          </button>
        </td>
      </tr>
      {update.error ? (
        <tr>
          <td colSpan={5}>
            <ErrorNotice error={update.error} />
          </td>
        </tr>
      ) : null}
      {resetting ? (
        <tr>
          <td colSpan={5}>
            <ResetPassword user={user} onDone={() => setResetting(false)} />
          </td>
        </tr>
      ) : null}
    </>
  );
}

function CreateUser() {
  const [username, setUsername] = useState("");
  const [role, setRole] = useState<Role>("regular");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [touched, setTouched] = useState(false);
  const problem = passwordProblem(password, confirm);
  const create = useMutation({
    mutationFn: () => unwrap(api.POST("/api/admin/users", { body: { username: username.trim(), role, password } })),
    onSuccess: () => {
      invalidateUsers();
      setUsername("");
      setRole("regular");
      setPassword("");
      setConfirm("");
      setTouched(false);
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (username.trim() && !problem) create.mutate();
  };
  return (
    <Section title="Add an account" id="new-user-h">
      <form onSubmit={submit} className="space-y-3">
        <div>
          <label htmlFor="nu-name" className="field-label">
            Username
          </label>
          <input
            id="nu-name"
            className="input"
            required
            autoComplete="off"
            pattern="[A-Za-z0-9_.\-]{3,64}"
            title="3–64 letters, digits, dots, dashes or underscores"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="nu-role" className="field-label">
            Role
          </label>
          <select id="nu-role" className="input" value={role} onChange={(e) => setRole(e.target.value as Role)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABEL[r]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="nu-pw" className="field-label">
            Password <span className="font-normal text-muted">(at least {PASSWORD_MIN} characters)</span>
          </label>
          <input
            id="nu-pw"
            type="password"
            autoComplete="new-password"
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="nu-pw2" className="field-label">
            Repeat password
          </label>
          <input
            id="nu-pw2"
            type="password"
            autoComplete="new-password"
            className="input"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </div>
        <div aria-live="polite">
          {touched && problem ? <p className="text-danger">{problem}</p> : null}
          <ErrorNotice error={create.error} />
          {create.isSuccess ? <Notice>Account created for {create.data.username}.</Notice> : null}
        </div>
        <button type="submit" className="btn btn-primary" disabled={create.isPending}>
          {create.isPending ? "Creating…" : "Create account"}
        </button>
      </form>
    </Section>
  );
}

export default function AdminUsersPage() {
  const me = useMe();
  const users = useAdminUsers();
  return (
    <>
      <PageHeader
        title="Users"
        lead={
          <>
            <strong>Admins</strong> manage accounts and settings. <strong>Power users</strong> can change or remove
            anyone's questions and assessments. <strong>Teachers</strong> can only change their own.
          </>
        }
      />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-5">
          <Section title="Accounts" id="users-h">
            <ErrorNotice error={users.error} />
            {users.isPending ? (
              <Loading />
            ) : (
              <div className="overflow-x-auto">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Username</th>
                      <th scope="col">Role</th>
                      <th scope="col">Status</th>
                      <th scope="col">Last sign-in</th>
                      <th scope="col">
                        <span className="sr-only">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.data?.map((u) => (
                      <UserRow key={u.id} user={u} isSelf={u.id === me.data?.id} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>
          <RegistrationCard />
        </div>
        <CreateUser />
      </div>
    </>
  );
}

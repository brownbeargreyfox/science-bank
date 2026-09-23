import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";

/** Raised by `unwrap` for any non-2xx response. `message` is already human-readable. */
export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type Unauthorized = () => void;
let onUnauthorized: Unauthorized = () => {};

/** The auth layer registers a callback that runs whenever a session has expired. */
export function setUnauthorizedHandler(fn: Unauthorized) {
  onUnauthorized = fn;
}

const authMiddleware: Middleware = {
  onResponse({ request, response }) {
    // A 401 from the login form means "wrong password", not "session expired".
    if (response.status === 401 && !new URL(request.url).pathname.endsWith("/api/auth/login")) {
      onUnauthorized();
    }
    return undefined;
  },
};

export const api = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? "",
  credentials: "include",
});
api.use(authMiddleware);

function humanLoc(loc: unknown): string {
  if (!Array.isArray(loc)) return "";
  const parts = loc.filter((p) => p !== "body" && p !== "query" && p !== "path");
  return parts
    .map((p) => (typeof p === "number" ? `#${p + 1}` : String(p).replaceAll("_", " ")))
    .join(" › ");
}

/** Turns `{detail: string}` or FastAPI's validation array into one readable sentence. */
export function describeError(error: unknown, status?: number): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          if (d && typeof d === "object") {
            const item = d as { loc?: unknown; msg?: unknown };
            const where = humanLoc(item.loc);
            const msg = typeof item.msg === "string" ? item.msg : "Invalid value";
            return where ? `${where}: ${msg}` : msg;
          }
          return String(d);
        })
        .join("; ");
    }
  }
  if (typeof error === "string" && error.trim()) return error;
  if (status === 401) return "Your session has ended. Log in again.";
  if (status === 404) return "That item no longer exists.";
  if (status && status >= 500) return `The server hit an error (HTTP ${status}). Try again in a moment.`;
  return status ? `Request failed (HTTP ${status}).` : "Could not reach the server. Check that the backend is running.";
}

/** Awaits an openapi-fetch call and returns its data or throws an ApiError. */
export async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let result: { data?: T; error?: unknown; response: Response };
  try {
    result = await call;
  } catch {
    throw new ApiError(0, describeError(undefined));
  }
  const { data, error, response } = result;
  if (!response.ok || error !== undefined) {
    throw new ApiError(response.status, describeError(error, response.status));
  }
  return data as T;
}

export function errorText(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}

/** Drops null/undefined/"" so FastAPI never receives `course_id=null`. */
export function cleanQuery<T extends Record<string, unknown>>(q: T): T {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(q)) {
    if (v === null || v === undefined || v === "") continue;
    if (Array.isArray(v) && v.length === 0) continue;
    out[k] = v;
  }
  return out as T;
}

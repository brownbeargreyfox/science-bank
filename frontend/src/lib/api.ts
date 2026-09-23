const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    ...init,
  });
}

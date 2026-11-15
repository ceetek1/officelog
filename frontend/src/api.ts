// Tiny API client. Cookies carry the session; every change sends the CSRF token (spec §8).

export type Role = "worker" | "manager" | "md";
export interface User { id: number; name: string; role: Role }
export interface Me { user: User | null; csrf_token: string | null; company: string }

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

let csrfToken: string | null = null;
export function setCsrf(token: string | null) { csrfToken = token; }

export async function api<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers,
      credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "offline", "No connection. Check the internet and try again.");
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const d = data && data.detail;
    const code = (d && d.code) || "error";
    const message = (d && d.message) || "Something went wrong. Try again.";
    throw new ApiError(res.status, code, message);
  }
  return data as T;
}

export const getMe = () => api<Me>("GET", "/api/auth/me");
export const passwordLogin = (email: string, password: string) =>
  api<Me>("POST", "/api/auth/password-login", { email, password });
export const logout = () => api<{ ok: true }>("POST", "/api/auth/logout");

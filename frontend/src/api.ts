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

// ---- Phone: invites and Face ID (decision D1) ----

export interface InviteInfo { name: string; invited_by: string | null; company: string }
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Json = any;
export interface Challenge { challenge_id: number; options: Json }

export const getInvite = (token: string) => api<InviteInfo>("GET", `/api/invites/${encodeURIComponent(token)}`);
export const inviteOptions = (token: string) => api<Challenge>("POST", `/api/invites/${encodeURIComponent(token)}/options`);
export const inviteRegister = (token: string, challenge_id: number, credential: Json) =>
  api<Me>("POST", `/api/invites/${encodeURIComponent(token)}/register`, { challenge_id, credential, privacy_ack: true });

export const passkeyOptions = () => api<Challenge>("POST", "/api/auth/passkey/options");
export const passkeyLogin = (challenge_id: number, credential: Json) =>
  api<Me>("POST", "/api/auth/passkey/login", { challenge_id, credential });

// ---- Phone: today and clocking ----

export interface Today {
  name: string;
  work_date: string;
  date: string;
  working_day: boolean;
  holiday: boolean;
  schedule: { start: string; grace_minutes: number; on_time_until: string; close: string } | null;
  clock_in: { time: string; at: string; source: string; late_minutes: number | null } | null;
  clock_out: { time: string; at: string; source: string; left_early_minutes: number | null } | null;
  worked_minutes: number | null;
  server_time: string;
}
export type Kind = "in" | "out";
export type Method = "qr" | "typed";
export interface Receipt {
  kind: Kind; time: string; date: string; working_day: boolean;
  late_minutes: number | null; left_early_minutes: number | null; worked_minutes: number | null;
}

export const getToday = () => api<Today>("GET", "/api/me/today");
export const clockStart = (kind: Kind, method: Method, code: string, confirm: boolean) =>
  api<Challenge>("POST", "/api/clock/start", { kind, method, code, confirm });
export const clockFinish = (challenge_id: number, credential: Json, client_ms_to_scan: number) =>
  api<Receipt>("POST", "/api/clock/finish", { challenge_id, credential, client_ms_to_scan });

// ---- Entrance TV ----

export interface KioskCode {
  qr: string; qr_ms_left: number; typed: string; typed_ms_left: number; typed_step_ms: number;
  greeting: string; date: string; time: string;
  recent: { id: number; name: string; time: string; kind: Kind }[];
  version: string;
}
export const kioskCode = () => api<KioskCode>("GET", "/api/kiosk/code");
export const kioskPair = (token: string) => api<{ ok: true }>("POST", "/api/kiosk/pair", { token });

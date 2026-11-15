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

export type DayStatus = "on_time" | "late" | "excused" | "absent" | "not_in_yet" | "day_off";
export interface Day {
  date: string;
  label: string;
  working_day: boolean;
  status: DayStatus;
  clock_in: { time: string; at: string; source: string; entered_by: string | null } | null;
  clock_out: { time: string; at: string; source: string; entered_by: string | null; approved_by: string | null } | null;
  late_minutes: number | null;
  late_excused: boolean;
  absent: boolean;
  absent_excused: boolean;
  missing_clock_out: boolean;
  left_early_minutes: number | null;
  left_early_excused: boolean;
  worked_minutes: number | null;
  not_in_yet: boolean;
  reasons: Record<string, "waiting" | "approved" | "rejected">;
}
export interface Today extends Day {
  name: string;
  work_date: string;
  holiday: boolean;
  schedule: { start: string; grace_minutes: number; on_time_until: string; close: string } | null;
  server_time: string;
}
export interface History {
  month: string; label: string; prev: string | null; next: string | null;
  summary: { days_in: number; late: number; left_early: number; absent: number; worked_minutes: number };
  days: Day[];
}
export interface TeamToday {
  work_date: string; date: string; working_day: boolean;
  counts: Record<DayStatus, number>;
  people: (Day & { user_id: number; name: string; role: Role })[];
}
export type Kind = "in" | "out";
export type Method = "qr" | "typed";
export interface Receipt {
  kind: Kind; time: string; date: string; working_day: boolean;
  late_minutes: number | null; left_early_minutes: number | null; worked_minutes: number | null;
}

export const getToday = () => api<Today>("GET", "/api/me/today");
export const getHistory = (month?: string) =>
  api<History>("GET", "/api/me/history" + (month ? `?month=${encodeURIComponent(month)}` : ""));
export const getTeamToday = () => api<TeamToday>("GET", "/api/team/today");
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

// ---- Reasons and approvals (spec §4.3) ----

export type ReasonType = "late" | "absent" | "left_early" | "missed_clock_out";
export type ReasonState = "waiting" | "approved" | "rejected";
export interface DecisionRow { id: number; decision: "approved" | "rejected"; by: string; note: string; is_override: boolean; at: string }
export interface Reason {
  id: number; user_id: number; name: string; role: Role;
  work_date: string; day_label: string; type: ReasonType; type_label: string; detail: string | null;
  clock_in: string | null; claimed_time: string | null; text: string;
  state: ReasonState; decisions: DecisionRow[]; editable: boolean; created_at: string;
}
export interface Approvals { waiting: Reason[]; decided: Reason[]; can_override: boolean }

export const getMyReasons = () => api<{ reasons: Reason[]; decided_by: string }>("GET", "/api/reasons/mine");
export const sendReason = (work_date: string, type: ReasonType, text: string, claimed_time?: string) =>
  api<Reason>("POST", "/api/reasons", { work_date, type, text, claimed_time: claimed_time || null });
export const editReason = (id: number, text: string, claimed_time?: string | null) =>
  api<{ ok: true }>("PUT", `/api/reasons/${id}`, { text, claimed_time: claimed_time || null });
export const getApprovals = () => api<Approvals>("GET", "/api/approvals");
export const decide = (id: number, decision: "approved" | "rejected", note: string) =>
  api<{ ok: true }>("POST", `/api/reasons/${id}/decision`, { decision, note });
export const overrideDecision = (id: number, decision: "approved" | "rejected", note: string) =>
  api<{ ok: true }>("POST", `/api/reasons/${id}/override`, { decision, note });

// ---- Activity log (MD) ----

export interface ActivityEntry { id: number; when: string; at: string; who: string; action: string; label: string; tone: string; details: string }
export const getActivity = (filter: string, before?: number) =>
  api<{ entries: ActivityEntry[]; more: boolean }>("GET",
    `/api/activity?filter=${encodeURIComponent(filter)}${before ? `&before=${before}` : ""}`);

// ---- People and the entrance TV (manager; spec §4.4) ----

export type PersonStatus = "active" | "invited" | "expired" | "off";
export interface Person {
  id: number; name: string; role: Role; status: PersonStatus; label: string; is_me: boolean;
  invite_expires: string | null;
}
export interface Invite { id: number; name: string; link: string; expires: string }
export const getPeople = () => api<{ people: Person[]; active_count: number }>("GET", "/api/people");
export const addPerson = (name: string) => api<Invite>("POST", "/api/people", { name });
export const resetPhone = (id: number) => api<Invite>("POST", `/api/people/${id}/reset-phone`);
export const deactivatePerson = (id: number) => api<{ id: number; active: false }>("POST", `/api/people/${id}/deactivate`);

export interface Tv {
  id: number; status: "online" | "offline" | "waiting"; label: string;
  set_up: string | null; last_seen: string | null; link_expires: string | null;
}
export interface TvLink { id: number; code: string; link: string; tv_page: string; expires: string }
export const getTvs = () => api<{ tvs: Tv[]; scans_today: number }>("GET", "/api/kiosks");
export const createTvLink = () => api<TvLink>("POST", "/api/kiosks");
export const removeTv = (id: number) => api<{ ok: true }>("POST", `/api/kiosks/${id}/revoke`);

// ---- Time from the paper sheet (decision D3; manager and MD) ----

export type PaperReason = "tv_not_working" | "no_smartphone" | "phone_dead_or_forgotten";
export interface PaperTimeEntry { time: string; source: string; entered_by: string | null }
export interface PaperDay {
  date: string; label: string;
  days: { date: string; label: string }[];
  reasons: { value: PaperReason; label: string }[];
  people: { user_id: number; name: string; is_me: boolean; clock_in: PaperTimeEntry | null; clock_out: PaperTimeEntry | null }[];
}
export const getPaperDay = (date?: string) =>
  api<PaperDay>("GET", "/api/paper/day" + (date ? `?date=${encodeURIComponent(date)}` : ""));
export const addPaperTime = (user_id: number, work_date: string, clock_in: string | null, clock_out: string | null,
  reason: PaperReason) =>
  api<{ name: string; added: { kind: Kind; time: string }[]; reason_label: string }>("POST", "/api/paper",
    { user_id, work_date, clock_in, clock_out, reason });

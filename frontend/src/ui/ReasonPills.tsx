import type { Reason, ReasonState } from "../api";
import { Pill } from "./Pill";

export function StatePill({ state }: { state: ReasonState }) {
  if (state === "approved") return <Pill tone="ok">Approved</Pill>;
  if (state === "rejected") return <Pill tone="bad">Rejected</Pill>;
  return <Pill tone="wait">Waiting</Pill>;
}

/** "Late · 23 min", "Missed clock-out · claimed 18:10". */
export function reasonHeadline(r: Reason): string {
  if (r.type === "missed_clock_out" && r.claimed_time) return `${r.type_label} · claimed ${r.claimed_time}`;
  return r.detail ? `${r.type_label} · ${r.detail}` : r.type_label;
}

export function TypePill({ r }: { r: Reason }) {
  const tone = r.type === "absent" ? "bad" : r.type === "missed_clock_out" ? "wait" : "warn";
  return <Pill tone={tone}>{reasonHeadline(r)}</Pill>;
}

export function decisionLine(d: { decision: string; by: string; at: string; note: string; is_override: boolean }): string {
  const when = new Date(d.at);
  const t = when.toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Africa/Lagos" });
  const word = d.decision === "approved" ? "Approved" : "Rejected";
  return `${d.is_override ? "Override: " : ""}${word} by ${d.by.split(" ")[0]} · ${t}${d.note ? ` · “${d.note}”` : ""}`;
}

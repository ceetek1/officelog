// The status words for a day (spec §10: always a word plus a tint, never colour alone).
import type { Day } from "../api";
import { Pill } from "./Pill";

/** The single most important word for a day, for lists. */
export function MainPill({ d }: { d: Day }) {
  if (d.absent) return d.absent_excused ? <Pill tone="excused">Excused</Pill> : <Pill tone="bad">Absent</Pill>;
  if (d.missing_clock_out) return <Pill tone="warn">No clock-out</Pill>;
  if (d.late_minutes !== null) return d.late_excused ? <Pill tone="excused">Excused</Pill> : <Pill tone="warn">Late</Pill>;
  if (d.left_early_minutes !== null) return d.left_early_excused ? <Pill tone="excused">Excused</Pill> : <Pill tone="warn">Left early</Pill>;
  if (d.clock_in) return d.working_day ? <Pill tone="ok">On time</Pill> : <Pill tone="wait">Day off</Pill>;
  if (d.not_in_yet) return <Pill tone="wait">Not in yet</Pill>;
  return <Pill tone="wait">Day off</Pill>;
}

/** Every flag for one day, for the Today screen. */
export function AllPills({ d }: { d: Day }) {
  return (
    <>
      {d.absent && (d.absent_excused ? <Pill tone="excused">Absent · excused</Pill> : <Pill tone="bad">Absent</Pill>)}
      {d.late_minutes !== null && (d.late_excused
        ? <Pill tone="excused">Late · {d.late_minutes} min · excused</Pill>
        : <Pill tone="warn">Late · {d.late_minutes} min</Pill>)}
      {d.left_early_minutes !== null && (d.left_early_excused
        ? <Pill tone="excused">Left early · {d.left_early_minutes} min · excused</Pill>
        : <Pill tone="warn">Left early · {d.left_early_minutes} min</Pill>)}
      {d.missing_clock_out && <Pill tone="warn">No clock-out</Pill>}
    </>
  );
}

export type WordTone = "warn" | "bad" | "muted";

/** The one status word for a day in a list, or null when there is nothing to say (on time).
 *  Shown as coloured text next to the times: a word, never colour alone (spec §10). */
export function dayWord(d: Day, withMinutes = false): { text: string; tone: WordTone } | null {
  if (d.absent) return d.absent_excused ? { text: "Absent · excused", tone: "muted" } : { text: "Absent", tone: "bad" };
  if (d.missing_clock_out) return { text: "No clock-out", tone: "warn" };
  if (d.late_minutes !== null) {
    if (d.late_excused) return { text: "Late · excused", tone: "muted" };
    return { text: withMinutes ? `${d.late_minutes} min late` : "Late", tone: "warn" };
  }
  if (d.left_early_minutes !== null) {
    return d.left_early_excused ? { text: "Left early · excused", tone: "muted" } : { text: "Left early", tone: "warn" };
  }
  if (d.clock_in && !d.working_day) return { text: "Day off", tone: "muted" };
  if (d.not_in_yet) return { text: "Not in yet", tone: "muted" };
  if (!d.clock_in && !d.working_day) return { text: "Day off", tone: "muted" };
  return null;
}

export function Word({ w }: { w: { text: string; tone: WordTone } }) {
  const cls = w.tone === "warn" ? "word-warn" : w.tone === "bad" ? "word-bad" : "";
  return <span className={`list-row-sub ${cls}`} style={w.tone === "muted" ? { color: "var(--text-2)" } : undefined}>{w.text}</span>;
}

/** "added from paper by Emeka" / "claimed 17:40 · approved by Folake" (decision D3, spec §4.3). */
export function timeNotes(d: Day): string[] {
  const notes: string[] = [];
  if (d.clock_in?.source === "paper") notes.push(`Clock-in ${d.clock_in.time} added from paper by ${d.clock_in.entered_by}.`);
  if (d.clock_out?.source === "paper") notes.push(`Clock-out ${d.clock_out.time} added from paper by ${d.clock_out.entered_by}.`);
  if (d.clock_out?.source === "claimed") notes.push(`Clock-out claimed ${d.clock_out.time} · approved by ${d.clock_out.approved_by}.`);
  return notes;
}

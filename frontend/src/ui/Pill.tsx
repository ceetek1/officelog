// Status pill: always a word plus a tint, never colour alone.
import type { ReactNode } from "react";

export type Tone = "ok" | "warn" | "bad" | "excused" | "wait" | "info";

export function Pill({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

// Team today (2026 redesign). Refreshes every 30 seconds. Three counts in one card, then people in
// triage order: who needs a look first, the on-time list last. Each row: name, time, and one
// status word under the time (a word, never colour alone).
import { useCallback, useEffect, useState } from "react";
import { getTeamToday, type TeamToday } from "../../api";
import { firstName, initials } from "../../format";
import { Alert } from "../../ui/Alert";
import { Button } from "../../ui/Button";
import { dayWord, Word } from "../../ui/DayPills";
import { TabBar } from "../../ui/TabBar";
import { PaperTimeSheet } from "./PaperTime";

type Person = TeamToday["people"][number];

const SECTIONS: { title: string; pick: (p: Person) => boolean }[] = [
  { title: "Not in yet", pick: (p) => p.status === "not_in_yet" },
  { title: "Absent", pick: (p) => p.status === "absent" },
  { title: "Late", pick: (p) => p.status === "late" },
  { title: "Excused", pick: (p) => p.status === "excused" },
  { title: "On time", pick: (p) => p.status === "on_time" },
  { title: "Day off", pick: (p) => p.status === "day_off" },
];

function paperNote(p: Person): string | null {
  const paper = p.clock_in?.source === "paper" ? p.clock_in : p.clock_out?.source === "paper" ? p.clock_out : null;
  return paper ? `From paper · ${firstName(paper.entered_by || "")}` : null;
}

export function Team() {
  const [data, setData] = useState<TeamToday | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [paper, setPaper] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setData(await getTeamToday()); setError(null); } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    }
  }, []);
  useEffect(() => {
    void load();
    const id = setInterval(() => { if (document.visibilityState === "visible") void load(); }, 30_000);
    return () => clearInterval(id);
  }, [load]);

  const c = data?.counts;
  return (
    <div className="phone">
      <header className="phone-header">
        <div className="phone-header-top">
          <button type="button" className="btn btn-plain" style={{ fontSize: 17 }} onClick={() => setPaper(true)}>Add Time</button>
        </div>
        {data && <span className="eyebrow">{data.date}</span>}
        <h1 className="large-title">Team</h1>
      </header>
      <main className="phone-main" style={{ paddingTop: 12, gap: 20 }}>
        {error && (
          <div className="stack-16">
            <p className="error-text" role="alert">{error}</p>
            <Button variant="secondary" onClick={() => void load()}>Try Again</Button>
          </div>
        )}
        {data && c && (
          <>
            <dl className="summary">
              <div><dt>On time</dt><dd style={{ color: "var(--ok-fg)" }}>{c.on_time}</dd></div>
              <div><dt>Late</dt><dd style={{ color: c.late ? "var(--warn-fg)" : undefined }}>{c.late}</dd></div>
              {c.absent > 0
                ? <div><dt>Absent</dt><dd style={{ color: "var(--bad-fg)" }}>{c.absent}</dd></div>
                : <div><dt>Not in yet</dt><dd>{c.not_in_yet}</dd></div>}
            </dl>
            {SECTIONS.map(({ title, pick }) => {
              const people = data.people.filter(pick);
              if (!people.length) return null;
              return (
                <section key={title}>
                  <h2 className="group-title">{title}</h2>
                  <ul className="group" style={{ margin: 0, padding: 0, listStyle: "none" }}>
                    {people.map((p) => {
                      const w = p.status === "on_time" || p.status === "not_in_yet" || p.status === "day_off" ? null : dayWord(p, true);
                      const note = paperNote(p);
                      return (
                        <li key={p.user_id} className="list-row" style={{ minHeight: 60 }}>
                          <span className="person-initials" aria-hidden="true">{initials(p.name)}</span>
                          <span className="list-row-body">
                            <span className="two-line">
                              <span style={{ fontWeight: 600 }}>{p.name}</span>
                              {note && <span className="list-row-sub" style={{ color: "var(--text-2)" }}>{note}</span>}
                            </span>
                            <span className="list-row-right">
                              {p.clock_in
                                ? <span>{p.clock_in.time}{p.clock_out ? ` – ${p.clock_out.time}` : ""}</span>
                                : <span style={{ color: "var(--text-2)" }} aria-label="No clock-in">—</span>}
                              {w && <Word w={w} />}
                            </span>
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              );
            })}
            {data.people.length === 0 && <div className="group"><p className="empty-note">Nobody added yet.</p></div>}
          </>
        )}
      </main>
      <TabBar role="manager" />
      {paper && <PaperTimeSheet onClose={() => setPaper(false)}
        onSaved={(m) => { setPaper(false); setSaved(m); void load(); }} />}
      {saved && <Alert title="Time Added" message={saved} actions={[{ label: "OK", onPress: () => setSaved(null) }]} />}
    </div>
  );
}

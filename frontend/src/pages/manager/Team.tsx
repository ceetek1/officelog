// Team today (Prototype B "Manager · Team today"; spec §10). Refreshes every 30 seconds.
import { useCallback, useEffect, useState } from "react";
import { getTeamToday, type TeamToday } from "../../api";
import { initials } from "../../format";
import { Button } from "../../ui/Button";
import { MainPill } from "../../ui/DayPills";
import { Pill } from "../../ui/Pill";
import { StatCards } from "../../ui/StatCards";
import { TabBar } from "../../ui/TabBar";

type Person = TeamToday["people"][number];

const SECTIONS: { title: string; pick: (p: Person) => boolean }[] = [
  { title: "Not in yet", pick: (p) => p.status === "not_in_yet" },
  { title: "Absent", pick: (p) => p.status === "absent" },
  { title: "Late", pick: (p) => p.status === "late" },
  { title: "Excused", pick: (p) => p.status === "excused" },
  { title: "On time", pick: (p) => p.status === "on_time" },
  { title: "Day off", pick: (p) => p.status === "day_off" },
];

export function Team() {
  const [data, setData] = useState<TeamToday | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <div className="phone">
      <header className="phone-header">
        <div className="phone-header-top" />
        {data && <span className="eyebrow">{data.date}</span>}
        <h1 className="large-title">Team</h1>
      </header>
      <main className="phone-main">
        {error && (
          <div className="stack-16">
            <p className="error-text" role="alert">{error}</p>
            <Button variant="secondary" onClick={() => void load()}>Try Again</Button>
          </div>
        )}
        {data && (
          <>
            <StatCards stats={[
              { label: "On time", value: data.counts.on_time, color: "var(--ok-fg)" },
              { label: "Late", value: data.counts.late, color: "var(--warn-fg)" },
              data.counts.absent > 0
                ? { label: "Absent", value: data.counts.absent, color: "var(--bad-fg)" }
                : { label: "Not in yet", value: data.counts.not_in_yet },
            ]} />
            {SECTIONS.map(({ title, pick }) => {
              const people = data.people.filter(pick);
              if (!people.length) return null;
              return (
                <section key={title}>
                  <h2 className="group-title">{title}</h2>
                  <div className="group">
                    {people.map((p) => (
                      <div key={p.user_id} className="row" style={{ minHeight: 56 }}>
                        <span className="person-initials" aria-hidden="true">{initials(p.name)}</span>
                        <span className="row-body">
                          <span className="two-line">
                            <span style={{ fontWeight: 600 }}>{p.name}</span>
                            {p.clock_in?.source === "paper" && <span className="sub-note">Added from paper</span>}
                          </span>
                          <span className="row-right">
                            <span className="mono">
                              {p.clock_in ? p.clock_in.time : "--:--"}{p.clock_out ? ` – ${p.clock_out.time}` : ""}
                            </span>
                            {p.status === "late" && <Pill tone="warn">{p.late_minutes} min</Pill>}
                            {p.status !== "late" && p.status !== "on_time" && p.status !== "not_in_yet"
                              && p.status !== "absent" && p.status !== "day_off" && <MainPill d={p} />}
                            {p.missing_clock_out && <Pill tone="warn">No clock-out</Pill>}
                            {p.left_early_minutes !== null && !p.missing_clock_out && <Pill tone="warn">Left early</Pill>}
                          </span>
                        </span>
                      </div>
                    ))}
                  </div>
                </section>
              );
            })}
            {data.people.length === 0 && <div className="group"><p className="empty-note">Nobody added yet.</p></div>}
          </>
        )}
      </main>
      <TabBar role="manager" />
    </div>
  );
}

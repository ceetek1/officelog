// History by month (Prototype B "11 · History by month"; spec §10).
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getHistory, type History as HistoryData, type Role } from "../../api";
import { Button } from "../../ui/Button";
import { dayWord, Word } from "../../ui/DayPills";
import { ChevronLeft, ChevronRight } from "../../ui/icons";
import { TabBar } from "../../ui/TabBar";

export function History({ role }: { role: Role }) {
  const navigate = useNavigate();
  const [month, setMonth] = useState<string | undefined>(undefined);
  const [data, setData] = useState<HistoryData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getHistory(month).then((d) => { if (alive) { setData(d); setError(null); } })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : "Something went wrong."); });
    return () => { alive = false; };
  }, [month]);

  const manager = role === "manager";
  return (
    <div className="phone">
      {manager ? (
        <div className="navbar">
          <button type="button" className="btn btn-plain" onClick={() => navigate("/")}><ChevronLeft />Me</button>
          <span className="navbar-title">History</span>
        </div>
      ) : (
        <header className="phone-header">
          <div className="phone-header-top" />
          <h1 className="large-title">History</h1>
        </header>
      )}
      <main className="phone-main">
        {error && (
          <div className="stack-16">
            <p className="error-text" role="alert">{error}</p>
            <Button variant="secondary" onClick={() => setMonth(month)}>Try Again</Button>
          </div>
        )}
        {data && (
          <>
            <div className="month-switch">
              <button type="button" className="icon-button" aria-label="Previous month" disabled={!data.prev}
                onClick={() => data.prev && setMonth(data.prev)}><ChevronLeft /></button>
              <span style={{ fontWeight: 600 }} aria-live="polite">{data.label}</span>
              <button type="button" className="icon-button" aria-label="Next month" disabled={!data.next}
                onClick={() => data.next && setMonth(data.next)}><ChevronRight size={26} /></button>
            </div>
            <dl className="summary">
              <div><dt>Days in</dt><dd>{data.summary.days_in}</dd></div>
              <div><dt>Late</dt><dd>{data.summary.late}</dd></div>
              <div><dt>Left early</dt><dd>{data.summary.left_early}</dd></div>
            </dl>
            {data.days.length === 0 ? (
              <div className="group"><p className="empty-note">Nothing yet this month.</p></div>
            ) : (
              <ul className="group" style={{ margin: 0, padding: 0, listStyle: "none" }}>
                {data.days.map((d) => {
                  const w = dayWord(d);
                  const note = d.clock_out?.source === "claimed" ? "Clock-out claimed"
                    : (d.clock_in?.source === "paper" || d.clock_out?.source === "paper") ? "From paper" : null;
                  return (
                    <li key={d.date} className="list-row">
                      <span className="list-row-body">
                        <span className="two-line">
                          <span>{d.label}</span>
                          {w && <Word w={w} />}
                        </span>
                        <span className="list-row-right">
                          {d.clock_in || d.clock_out
                            ? <span>{d.clock_in ? d.clock_in.time : "—"} – {d.clock_out ? d.clock_out.time : "—"}</span>
                            : <span style={{ color: "var(--text-2)" }} aria-label="No times">—</span>}
                          {note && <span className="list-row-sub" style={{ color: "var(--text-2)" }}>{note}</span>}
                        </span>
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </>
        )}
      </main>
      {!manager && <TabBar role={role} />}
    </div>
  );
}

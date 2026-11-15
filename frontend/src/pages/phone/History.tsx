// History by month (Prototype B "11 · History by month"; spec §10).
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getHistory, type History as HistoryData, type Role } from "../../api";
import { Button } from "../../ui/Button";
import { MainPill } from "../../ui/DayPills";
import { ChevronLeft, ChevronRight } from "../../ui/icons";
import { StatCards } from "../../ui/StatCards";
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
            <StatCards stats={[
              { label: "Days in", value: data.summary.days_in },
              { label: "Late", value: data.summary.late },
              { label: "Left early", value: data.summary.left_early },
            ]} />
            {data.days.length === 0 ? (
              <div className="group"><p className="empty-note">Nothing yet this month.</p></div>
            ) : (
              <div className="group">
                {data.days.map((d) => (
                  <div key={d.date} className="row" style={{ minHeight: 60 }}>
                    <span className="row-body">
                      <span className="two-line">
                        <span style={{ fontWeight: 600 }}>{d.label}</span>
                        <span className="sub-mono">
                          {d.clock_in ? d.clock_in.time : "--:--"} – {d.clock_out ? d.clock_out.time : "--:--"}
                        </span>
                        {(d.clock_in?.source === "paper" || d.clock_out?.source === "paper") && (
                          <span className="sub-note">Added from paper</span>
                        )}
                        {d.clock_out?.source === "claimed" && <span className="sub-note">Clock-out claimed, approved</span>}
                      </span>
                      <span className="row-right"><MainPill d={d} /></span>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </main>
      {!manager && <TabBar role={role} />}
    </div>
  );
}

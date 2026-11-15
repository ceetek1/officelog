// MD · history per person (Prototype B "MD · person history"; spec §10). Month by month.
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getPersonHistory, type PersonHistory } from "../../api";
import { worked } from "../../format";
import { MainPill } from "../../ui/DayPills";
import { ChevronLeft, ChevronRight } from "../../ui/icons";
import { Pill } from "../../ui/Pill";
import { PHONE, useMedia } from "../../ui/useMedia";
import { MdShell } from "./Shell";

type Day = PersonHistory["days"][number];

function Status({ d }: { d: Day }) {
  if (d.late_minutes !== null && !d.late_excused && !d.missing_clock_out && !d.absent)
    return <Pill tone="warn">Late · {d.late_minutes} min</Pill>;
  return <MainPill d={d} />;
}

const t = (x: Day["clock_in"]) => x
  ? <span className="mono" style={{ fontWeight: 700 }}>{x.time}</span>
  : <span className="mono" style={{ color: "var(--text-3)" }}>--:--</span>;

export function MdPersonHistory() {
  const { id = "" } = useParams();
  const phone = useMedia(PHONE);
  const [month, setMonth] = useState<string | undefined>(undefined);
  const [data, setData] = useState<PersonHistory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try { setData(await getPersonHistory(Number(id), month)); setError(null); } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    }
  }, [id, month]);
  useEffect(() => { void load(); }, [load]);

  const p = data?.person;
  const sub = p && `${p.role === "manager" ? "Manager" : "Worker"}${!p.active ? " · deactivated" : ""}`
    + (p.phone_registered ? ` · phone registered ${p.phone_registered}` : " · no phone registered");
  const switcher = data && (
    <div className="month-switch" style={{ gap: 8 }}>
      <button type="button" className="icon-button" aria-label="Previous month" disabled={!data.prev}
        onClick={() => data.prev && setMonth(data.prev)}><ChevronLeft /></button>
      <span style={{ fontWeight: 600, minWidth: 130, textAlign: "center" }}>{data.label}</span>
      <button type="button" className="icon-button" aria-label="Next month" disabled={!data.next}
        onClick={() => data.next && setMonth(data.next)}><ChevronRight /></button>
    </div>
  );

  return (
    <MdShell title={p?.name || "Person"} subtitle={sub || undefined} back={{ to: "/md", label: "Today" }} actions={switcher} phoneActions={switcher}>
      {error && <p className="error-text" role="alert">{error}</p>}
      {data && (
        <>
          <div className={`stats stats-4${phone ? " stats-compact" : ""}`} style={phone ? { gridTemplateColumns: "repeat(4, minmax(0, 1fr))" } : undefined}>
            {[{ label: "Days in", value: data.summary.days_in },
              { label: "Late", value: data.summary.late, color: data.summary.late ? "var(--warn-fg)" : undefined },
              { label: "Excused", value: data.summary.excused, color: data.summary.excused ? "var(--excused-fg)" : undefined },
              { label: "Worked", value: `${Math.round(data.summary.worked_minutes / 60)} h` }].map((s) => (
              <div key={s.label} className="stat"><span className="stat-label">{s.label}</span>
                <span className="stat-value" style={s.color ? { color: s.color } : undefined}>{s.value}</span></div>
            ))}
          </div>
          {phone ? (
            <div className="group">
              {data.days.map((d) => (
                <div key={d.date} className="row" style={{ minHeight: 60 }}>
                  <span className="row-body">
                    <span className="two-line">
                      <span style={{ fontWeight: 600 }}>{d.label}</span>
                      <span className="mono" style={{ fontWeight: 500, color: "#404040", whiteSpace: "nowrap" }}>
                        {d.clock_in?.time || "--:--"} – {d.clock_out?.time || "--:--"}</span>
                      <span className="status-note">{d.note || (d.worked_minutes !== null ? worked(d.worked_minutes) : "")}</span>
                    </span>
                    <Status d={d} />
                  </span>
                </div>
              ))}
              {!data.days.length && <p className="empty-note">No days this month.</p>}
            </div>
          ) : (
            <div className="group">
              <div className="md-table-head md-person-cols"><span>Day</span><span>In</span><span>Out</span><span>Worked</span><span>Status</span><span>Reason or decision</span></div>
              {data.days.map((d) => (
                <div key={d.date} className="md-table-row md-person-cols">
                  <span style={{ fontWeight: 600 }}>{d.label}</span>
                  {t(d.clock_in)}{t(d.clock_out)}
                  <span>{d.worked_minutes !== null ? worked(d.worked_minutes) : "--"}</span>
                  <span><Status d={d} /></span>
                  <span className="status-note">{d.note}</span>
                </div>
              ))}
              {!data.days.length && <p className="empty-note">No days this month.</p>}
            </div>
          )}
        </>
      )}
    </MdShell>
  );
}

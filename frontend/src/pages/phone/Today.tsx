// Today (2026 redesign): one status card whose layout never changes between states, one status
// line instead of a row of pills, and the big button in the thumb zone. Clock In is green,
// Clock Out is dark, and when the day is done there is no button.
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, getToday, logout, type Kind, type ReasonType, type Role, type Today as TodayData } from "../../api";
import { initials, worked } from "../../format";
import { useSession } from "../../session";
import { Alert } from "../../ui/Alert";
import { Button } from "../../ui/Button";
import { clockTime, DayLine } from "../../ui/DayLine";
import { timeNotes } from "../../ui/DayPills";
import { CheckIcon, ChevronRight, ScanIcon } from "../../ui/icons";
import { StatePill } from "../../ui/ReasonPills";
import { ActionSheet } from "../../ui/Sheets";
import { TabBar } from "../../ui/TabBar";
import { AddReason } from "./AddReason";
import { ClockFlow } from "./ClockFlow";

const REASON_LABEL: Record<string, string> = {
  late: "Late reason", absent: "Absence reason", left_early: "Left early reason", missed_clock_out: "Missed clock-out",
};
const ADD_LABEL: Record<ReasonType, string> = {
  late: "Add a reason for being late", absent: "Add a reason for being absent",
  left_early: "Add a reason for leaving early", missed_clock_out: "Add the time you left",
};

const CONFIRM_WITHIN_MS = 5 * 60 * 1000;

function Chevron() {
  return <span className="row-chevron"><ChevronRight size={20} /></span>;
}

export function Today({ role }: { role: Role }) {
  const { refresh } = useSession();
  const navigate = useNavigate();
  const [today, setToday] = useState<TodayData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [flow, setFlow] = useState<{ kind: Kind; confirm: boolean; t0: number } | null>(null);
  const [askConfirm, setAskConfirm] = useState(false);
  const [menu, setMenu] = useState(false);
  const [adding, setAdding] = useState<ReasonType | null>(null);
  // The server's clock, carried forward with the phone's: drives the "now" dot on the day line.
  const [offset, setOffset] = useState(0);
  const [, setTick] = useState(0);

  const load = useCallback(async () => {
    try {
      const t = await getToday();
      setToday(t);
      setOffset(new Date(t.server_time).getTime() - Date.now());
      setError(null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) await refresh();
      else setError(e instanceof Error ? e.message : "Something went wrong.");
    }
  }, [refresh]);

  useEffect(() => {
    void load();
    const onVisible = () => { if (document.visibilityState === "visible") void load(); };
    document.addEventListener("visibilitychange", onVisible);
    const id = setInterval(() => setTick((n) => n + 1), 60_000);
    return () => { document.removeEventListener("visibilitychange", onVisible); clearInterval(id); };
  }, [load]);

  async function signOut() {
    setMenu(false);
    try { await logout(); } finally { await refresh(); }
  }

  if (!today) {
    return (
      <div className="phone">
        <div className="center-screen">
          {error ? (<><p className="subtitle">{error}</p><Button onClick={() => void load()}>Try Again</Button></>) : null}
        </div>
      </div>
    );
  }

  const kind: Kind | null = !today.clock_in ? "in" : !today.clock_out ? "out" : null;

  function begin() {
    if (!kind || !today) return;
    const t0 = Date.now();
    if (kind === "out" && today.clock_in) {
      const since = new Date(today.server_time).getTime() - new Date(today.clock_in.at).getTime();
      if (since < CONFIRM_WITHIN_MS) { setAskConfirm(true); return; }
    }
    setFlow({ kind, confirm: false, t0 });
  }

  // Something that needs a reason, and has none yet.
  const needs: ReasonType | null =
    today.late_minutes !== null && !today.reasons.late ? "late"
    : today.left_early_minutes !== null && !today.reasons.left_early ? "left_early"
    : today.missing_clock_out && !today.reasons.missed_clock_out ? "missed_clock_out"
    : today.absent && !today.reasons.absent ? "absent" : null;
  const reasonRows = Object.entries(today.reasons);
  const notes = timeNotes(today);
  const now = clockTime(new Date(Date.now() + offset));
  const sched = today.schedule;

  // One headline and one status line.
  let title: string;
  let line: ReactNode = null;
  const done = !!today.clock_out;
  if (done) {
    title = "Done for today";
    line = (<>{worked(today.worked_minutes)} worked
      {today.left_early_minutes !== null && !today.left_early_excused && <> · <span className="word-warn">left {today.left_early_minutes} min early</span></>}</>);
  } else if (today.clock_in) {
    title = "Clocked in";
    const lateWord = today.late_minutes === null ? "On time"
      : today.late_excused ? "Late, excused" : <span className="word-warn">{today.late_minutes} min late</span>;
    line = <>{lateWord}{sched && <> · work ends {sched.close}</>}</>;
  } else if (today.absent) {
    title = "Absent";
    line = today.absent_excused ? "Excused" : "No clock-in today";
  } else if (!today.working_day) {
    title = today.holiday ? "Holiday" : "Day off";
    line = "Clock-ins are still recorded.";
  } else {
    title = "Not clocked in";
    line = sched ? <>On time until {sched.on_time_until}</> : null;
  }
  if (today.missing_clock_out) line = <span className="word-warn">No clock-out</span>;

  return (
    <div className="phone">
      <header className="phone-header">
        <div className="phone-header-top">
          <button type="button" className="avatar" aria-label={`Account, ${today.name}`} onClick={() => setMenu(true)}>
            <span aria-hidden="true">{initials(today.name)}</span>
          </button>
        </div>
        <span className="eyebrow">{today.date}</span>
        <h1 className="large-title">Today</h1>
      </header>
      <main className="phone-main" style={{ paddingTop: 12 }}>
        <section className="status-card" aria-label="Status">
          <div className="status-head-row">
            {done && <span className="done-check" aria-hidden="true"><CheckIcon size={18} /></span>}
            <div className="status-head">
              <h2 className="status-title">{title}</h2>
              {line && <p className="status-sub">{line}</p>}
            </div>
          </div>
          {sched && today.working_day && (
            <DayLine start={sched.start} close={sched.close} clockIn={today.clock_in?.time || null}
              clockOut={today.clock_out?.time || null} now={now} />
          )}
          <div className="tiles">
            <div className="tile">
              <span className="tile-label">Clock in</span>
              {today.clock_in ? <span className="tile-value">{today.clock_in.time}</span>
                : <span className="tile-value tile-empty" aria-label="Not yet">—</span>}
            </div>
            <div className="tile">
              <span className="tile-label">Clock out</span>
              {today.clock_out ? <span className="tile-value">{today.clock_out.time}</span>
                : <span className="tile-value tile-empty" aria-label="Not yet">—</span>}
            </div>
          </div>
        </section>
        {notes.length > 0 && <p className="group-footer" style={{ marginTop: -8 }}>{notes.join(" ")}</p>}

        {needs && (
          <button type="button" className="nav-row" onClick={() => setAdding(needs)}>
            <span className="dot-warn" aria-hidden="true" />
            <span className="nav-row-label">{ADD_LABEL[needs]}</span>
            <Chevron />
          </button>
        )}
        {reasonRows.map(([type, state]) => (
          <Link key={type} to="/reasons" className="nav-row">
            <span className="nav-row-label">{REASON_LABEL[type] || type}</span>
            <StatePill state={state} />
            <Chevron />
          </Link>
        ))}

        {role === "manager" && (
          <div className="group">
            <Link to="/history" className="list-row">
              <span className="list-row-body"><span>My History</span><Chevron /></span>
            </Link>
            <Link to="/reasons" className="list-row">
              <span className="list-row-body"><span>My Reasons</span><Chevron /></span>
            </Link>
          </div>
        )}
        {error && <p className="error-text" role="alert">{error}</p>}
      </main>
      {kind && (
        <div className="phone-footer phone-footer-above-tabs">
          <button type="button" className={`big-button${kind === "out" ? " big-button-dark" : ""}`} onClick={begin}>
            <ScanIcon size={22} /><span>{kind === "in" ? "Clock In" : "Clock Out"}</span>
          </button>
        </div>
      )}
      <TabBar role={role} />
      {askConfirm && today.clock_in && (
        <Alert
          title="Clock Out Now?"
          message={`You clocked in at ${today.clock_in.time}, less than 5 minutes ago.`}
          actions={[
            { label: "Cancel", cancel: true, onPress: () => setAskConfirm(false) },
            { label: "Clock Out", bold: true, onPress: () => { setAskConfirm(false); setFlow({ kind: "out", confirm: true, t0: Date.now() }); } },
          ]}
        />
      )}
      {menu && (
        <ActionSheet title={today.name} message="Signed in on this phone" onCancel={() => setMenu(false)}
          actions={[{ label: "Privacy", onPress: () => { setMenu(false); navigate("/privacy"); } },
            { label: "Sign Out", destructive: true, onPress: signOut }]} />
      )}
      {flow && (
        <ClockFlow kind={flow.kind} confirm={flow.confirm} t0={flow.t0}
          onClose={() => { setFlow(null); void load(); }}
          onAddReason={(t) => { setFlow(null); void load(); setAdding(t); }} />
      )}
      {adding && (
        <AddReason today={today.work_date} date={today.work_date} type={adding}
          onCancel={() => setAdding(null)} onDone={() => { setAdding(null); void load(); }} />
      )}
    </div>
  );
}

// Today: one big button (Clock In / Clock Out) or "Done for today" (spec §4.2).
// Prototype B boards "4 · Today: Clock in", "7 · Today: Clock out", "8 · Done for today".
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, getToday, logout, type Kind, type ReasonType, type Role, type Today as TodayData } from "../../api";
import { initials, worked } from "../../format";
import { useSession } from "../../session";
import { Alert } from "../../ui/Alert";
import { Button } from "../../ui/Button";
import { Group, Row } from "../../ui/Grouped";
import { AllPills, timeNotes } from "../../ui/DayPills";
import { ChevronRight, ScanIcon } from "../../ui/icons";
import { Pill } from "../../ui/Pill";
import { ActionSheet } from "../../ui/Sheets";
import { TabBar } from "../../ui/TabBar";
import { StatePill } from "../../ui/ReasonPills";
import { AddReason } from "./AddReason";
import { ClockFlow } from "./ClockFlow";

const REASON_LABEL: Record<string, string> = {
  late: "Late reason", absent: "Absence reason", left_early: "Left early reason", missed_clock_out: "Missed clock-out",
};

const CONFIRM_WITHIN_MS = 5 * 60 * 1000;

export function Today({ role }: { role: Role }) {
  const { refresh } = useSession();
  const [today, setToday] = useState<TodayData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [flow, setFlow] = useState<{ kind: Kind; confirm: boolean; t0: number } | null>(null);
  const [askConfirm, setAskConfirm] = useState(false);
  const [menu, setMenu] = useState(false);
  const [adding, setAdding] = useState<ReasonType | null>(null);

  const load = useCallback(async () => {
    try {
      setToday(await getToday());
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
    return () => document.removeEventListener("visibilitychange", onVisible);
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

  const notes = timeNotes(today);
  // Something that needs a reason, and has none yet.
  const needs: ReasonType | null =
    today.late_minutes !== null && !today.reasons.late ? "late"
    : today.left_early_minutes !== null && !today.reasons.left_early ? "left_early"
    : today.missing_clock_out && !today.reasons.missed_clock_out ? "missed_clock_out"
    : today.absent && !today.reasons.absent ? "absent" : null;
  const reasonRows = Object.entries(today.reasons);
  const footer = [!today.working_day ? "Not a working day. Clock-ins are still recorded." : "", ...notes]
    .filter(Boolean).join(" ");

  return (
    <div className="phone">
      <header className="phone-header">
        <div className="phone-header-top">
          <button type="button" className="avatar" aria-label={`Account: ${today.name}`} onClick={() => setMenu(true)}>
            <span aria-hidden="true">{initials(today.name)}</span>
          </button>
        </div>
        <span className="eyebrow">{today.date}</span>
        <h1 className="large-title">Today</h1>
      </header>
      <main className="phone-main">
        <div className="status-line">
          {!today.clock_in && <Pill tone="wait">Not clocked in</Pill>}
          {today.clock_in && !today.clock_out && <Pill tone="info">Clocked in</Pill>}
          {today.clock_out && <Pill tone="ok">Done for today</Pill>}
          <AllPills d={today} />
          {!today.working_day && <Pill tone="wait">{today.holiday ? "Holiday" : "Day off"}</Pill>}
          {!today.clock_in && today.schedule && (
            <span className="status-note">On time until {today.schedule.on_time_until}</span>
          )}
        </div>
        <Group footer={footer || undefined}>
          {!today.clock_in && today.schedule && <Row label="Work starts" value={today.schedule.start} mono />}
          <Row label="Clock in" mono value={today.clock_in
            ? <span className="row-strong">{today.clock_in.time}</span> : "--:--"} />
          <Row label="Clock out" mono value={today.clock_out
            ? <span className="row-strong">{today.clock_out.time}</span> : "--:--"} />
          {today.clock_in && !today.clock_out && today.schedule && <Row label="Work ends" value={today.schedule.close} mono />}
          {today.clock_out && <Row label="Worked" value={worked(today.worked_minutes)} />}
        </Group>
        {reasonRows.length > 0 && (
          <div className="group">
            {reasonRows.map(([type, state]) => (
              <Link key={type} to="/reasons" className="row">
                <span className="row-body"><span>{REASON_LABEL[type] || type}</span>
                  <span className="row-right"><StatePill state={state} />
                    <span style={{ color: "var(--text-4)", display: "flex" }}><ChevronRight /></span></span></span>
              </Link>
            ))}
          </div>
        )}
        {needs && <Button variant="secondary" onClick={() => setAdding(needs)}>Add a Reason</Button>}
        {role === "manager" && (
          <div className="group">
            <Link to="/history" className="row">
              <span className="row-body"><span>My History</span>
                <span style={{ color: "var(--text-4)", display: "flex" }}><ChevronRight /></span></span>
            </Link>
            <Link to="/reasons" className="row">
              <span className="row-body"><span>My Reasons</span>
                <span style={{ color: "var(--text-4)", display: "flex" }}><ChevronRight /></span></span>
            </Link>
          </div>
        )}
        {error && <p className="error-text" role="alert">{error}</p>}
      </main>
      {kind && (
        <div className="phone-footer">
          <button type="button" className={`big-button${kind === "out" ? " big-button-dark" : ""}`} onClick={begin}>
            <ScanIcon /><span>{kind === "in" ? "Clock In" : "Clock Out"}</span>
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
        <ActionSheet onCancel={() => setMenu(false)} actions={[{ label: "Sign Out", destructive: true, onPress: signOut }]} />
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

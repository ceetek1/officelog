// My reasons (Prototype B "10 · My reasons").
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getMyReasons, getToday, type Reason, type Role } from "../../api";
import { Button } from "../../ui/Button";
import { ChevronLeft, ChevronRight } from "../../ui/icons";
import { decisionLine, StatePill } from "../../ui/ReasonPills";
import { Sheet } from "../../ui/Sheets";
import { TabBar } from "../../ui/TabBar";
import { AddReason } from "./AddReason";

export function Reasons({ role }: { role: Role }) {
  const navigate = useNavigate();
  const [reasons, setReasons] = useState<Reason[] | null>(null);
  const [decidedBy, setDecidedBy] = useState("");
  const [today, setToday] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [open, setOpen] = useState<Reason | null>(null);
  const [editing, setEditing] = useState<Reason | null>(null);

  const load = useCallback(async () => {
    try {
      const [mine, t] = await Promise.all([getMyReasons(), getToday()]);
      setReasons(mine.reasons);
      setDecidedBy(mine.decided_by);
      setToday(t.work_date);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const manager = role === "manager";
  const plus = (
    <button type="button" className="icon-button" aria-label="New reason" onClick={() => setAdding(true)} disabled={!today}>
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
    </button>
  );
  return (
    <div className="phone">
      {manager ? (
        <div className="navbar">
          <button type="button" className="btn btn-plain" onClick={() => navigate("/")}><ChevronLeft />Me</button>
          <span className="navbar-title">My Reasons</span>
          <span style={{ position: "relative", zIndex: 1 }}>{plus}</span>
        </div>
      ) : (
        <header className="phone-header">
          <div className="phone-header-top">{plus}</div>
          <h1 className="large-title">My Reasons</h1>
        </header>
      )}
      <main className="phone-main">
        {error && <><p className="error-text" role="alert">{error}</p><Button variant="secondary" onClick={() => void load()}>Try Again</Button></>}
        {reasons && reasons.length === 0 && (
          <div className="group"><p className="empty-note">No reasons yet.</p></div>
        )}
        {reasons && reasons.length > 0 && (
          <div className="group">
            {reasons.map((r) => (
              <button key={r.id} type="button" className="row row-button" onClick={() => setOpen(r)}>
                <span className="row-body">
                  <span className="two-line"><span style={{ fontWeight: 600 }}>{r.type_label}</span>
                    <span className="status-note">{r.day_label}</span></span>
                  <span className="row-right"><StatePill state={r.state} />
                    <span style={{ color: "var(--text-4)", display: "flex" }}><ChevronRight /></span></span>
                </span>
              </button>
            ))}
          </div>
        )}
        {reasons && <p className="group-footer">Your reasons go to {decidedBy}.</p>}
      </main>
      {!manager && <TabBar role={role} />}
      {adding && today && (
        <AddReason today={today} onCancel={() => setAdding(false)} onDone={() => { setAdding(false); void load(); }} />
      )}
      {editing && today && (
        <AddReason today={today} editing={editing} onCancel={() => setEditing(null)}
          onDone={() => { setEditing(null); void load(); }} />
      )}
      {open && (
        <Sheet title={open.type_label} cancelLabel="Close" onCancel={() => setOpen(null)}
          right={open.editable ? <button type="button" className="btn btn-plain" onClick={() => { setEditing(open); setOpen(null); }}>Edit</button> : undefined}>
          <div className="sheet-body">
            <div className="status-line"><StatePill state={open.state} /><span className="status-note">{open.day_label}</span></div>
            {open.claimed_time && <p className="subtitle">Time you left: <span className="mono">{open.claimed_time}</span></p>}
            <div className="card"><p className="quote">“{open.text}”</p></div>
            {open.decisions.length > 0 && (
              <section>
                <h2 className="group-title">Decisions</h2>
                <div className="group">
                  {open.decisions.map((d) => (
                    <div key={d.id} className="row"><span className="row-body"><span style={{ fontSize: 15 }}>{decisionLine(d)}</span></span></div>
                  ))}
                </div>
                <p className="group-footer">The newest decision counts.</p>
              </section>
            )}
            {open.editable && <p className="group-footer">You can edit it until it's decided.</p>}
          </div>
        </Sheet>
      )}
    </div>
  );
}

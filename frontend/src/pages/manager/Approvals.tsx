// Manager · Approvals (Prototype B). Workers' reasons; the manager's own go to the MD.
import { useCallback, useEffect, useState } from "react";
import { ApiError, decide, getApprovals, type Approvals as Data, type Reason } from "../../api";
import { initials } from "../../format";
import { Button } from "../../ui/Button";
import { decisionLine, StatePill, TypePill } from "../../ui/ReasonPills";
import { TabBar, refreshBadge } from "../../ui/TabBar";

export function ReasonCard({ r, onDecided }: { r: Reason; onDecided: () => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function go(decision: "approved" | "rejected") {
    setBusy(true);
    setError(null);
    try { await decide(r.id, decision, note.trim()); onDecided(); } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong.");
    } finally { setBusy(false); }
  }
  return (
    <article className="card" aria-label={`${r.name}, ${r.type_label}`}>
      <div className="card-head">
        <span className="person-initials" aria-hidden="true">{initials(r.name)}</span>
        <span className="two-line" style={{ flexGrow: 1 }}>
          <span style={{ fontWeight: 600 }}>{r.name}</span>
          <span className="status-note">{r.day_label}{r.clock_in ? ` · in ${r.clock_in}` : ""}</span>
        </span>
      </div>
      <div><TypePill r={r} /></div>
      <p className="quote">“{r.text}”</p>
      <input className="note-input" type="text" placeholder="Note (optional)" maxLength={500} value={note}
        aria-label={`Note for ${r.name.split(" ")[0]}`} onChange={(e) => setNote(e.target.value)} />
      {error && <p className="error-text" role="alert">{error}</p>}
      <div className="two-buttons">
        <Button className="btn-reject" disabled={busy} onClick={() => go("rejected")}>Reject</Button>
        <Button disabled={busy} onClick={() => go("approved")}>Approve</Button>
      </div>
    </article>
  );
}

export function Approvals() {
  const [data, setData] = useState<Data | null>(null);
  const [tab, setTab] = useState<"waiting" | "decided">("waiting");
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try { setData(await getApprovals()); setError(null); refreshBadge(); } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return (
    <div className="phone">
      <header className="phone-header">
        <div className="phone-header-top" />
        <h1 className="large-title">Approvals</h1>
      </header>
      <div style={{ padding: "0 16px 8px" }}>
        <div className="segmented" role="tablist">
          <button type="button" role="tab" className="segment" aria-selected={tab === "waiting"} onClick={() => setTab("waiting")}>
            Waiting{data ? ` · ${data.waiting.length}` : ""}</button>
          <button type="button" role="tab" className="segment" aria-selected={tab === "decided"} onClick={() => setTab("decided")}>Decided</button>
        </div>
      </div>
      <main className="phone-main">
        {error && <><p className="error-text" role="alert">{error}</p><Button variant="secondary" onClick={() => void load()}>Try Again</Button></>}
        {data && tab === "waiting" && (data.waiting.length
          ? data.waiting.map((r) => <ReasonCard key={r.id} r={r} onDecided={() => void load()} />)
          : <div className="group"><p className="empty-note">Nothing waiting.</p></div>)}
        {data && tab === "decided" && (data.decided.length ? (
          <div className="group">
            {data.decided.map((r) => (
              <div key={r.id} className="row" style={{ minHeight: 60 }}>
                <span className="row-body">
                  <span className="two-line">
                    <span style={{ fontWeight: 600 }}>{r.name}</span>
                    <span className="status-note">{r.type_label} · {r.day_label}</span>
                    <span className="sub-note">{decisionLine(r.decisions[r.decisions.length - 1])}</span>
                  </span>
                  <span className="row-right"><StatePill state={r.state} /></span>
                </span>
              </div>
            ))}
          </div>
        ) : <div className="group"><p className="empty-note">Nothing decided yet.</p></div>)}
        <p className="group-footer" style={{ textAlign: "center" }}>Your own reasons go to the MD.</p>
      </main>
      <TabBar role="manager" />
    </div>
  );
}

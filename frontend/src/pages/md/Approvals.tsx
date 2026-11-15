// MD · Approvals + Override (Prototype B). The MD decides the manager's reasons (and may decide
// workers'), and can override any decision. Overrides add a decision; the newest one counts.
import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { ApiError, getApprovals, overrideDecision, type Approvals as Data, type Reason } from "../../api";
import { useSession } from "../../session";
import { Button } from "../../ui/Button";
import { ChevronRight } from "../../ui/icons";
import { decisionLine, StatePill, TypePill } from "../../ui/ReasonPills";
import { refreshBadge } from "../../ui/TabBar";
import { Sheet } from "../../ui/Sheets";
import { ReasonCard } from "../manager/Approvals";
import { MdShell } from "./Shell";

function useWide() {
  const q = "(min-width: 1000px)";
  const [wide, setWide] = useState(() => window.matchMedia(q).matches);
  useEffect(() => {
    const m = window.matchMedia(q);
    const on = () => setWide(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return wide;
}

function OverridePanel({ r, onSaved }: { r: Reason; onSaved: () => void }) {
  const current = r.state === "approved" ? "approved" : "rejected";
  const [choice, setChoice] = useState<"approved" | "rejected">(current === "approved" ? "rejected" : "approved");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setChoice(current === "approved" ? "rejected" : "approved"); setNote(""); setError(null); }, [r.id, current]);

  async function save() {
    setBusy(true);
    setError(null);
    try { await overrideDecision(r.id, choice, note.trim()); onSaved(); } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong.");
    } finally { setBusy(false); }
  }
  const latest = r.decisions[r.decisions.length - 1];
  return (
    <div className="stack-16">
      <div className="card">
        <div className="two-line"><span style={{ fontWeight: 600 }}>{r.name}</span>
          <span className="status-note">{r.day_label}{r.clock_in ? ` · in ${r.clock_in}` : ""}</span></div>
        <div><TypePill r={r} /></div>
        <p className="quote">“{r.text}”</p>
      </div>
      <section>
        <h2 className="group-title">History</h2>
        <div className="group">
          {r.decisions.map((d) => (
            <div key={d.id} className="row"><span className="row-body">
              <span style={{ fontSize: 15 }}>{decisionLine(d)}</span>
              {d === latest && <span className="sub-note" style={{ whiteSpace: "nowrap" }}>Counts now</span>}
            </span></div>
          ))}
        </div>
      </section>
      <section>
        <h2 className="group-title">Your decision</h2>
        <div className="segmented" role="radiogroup" aria-label="Your decision">
          {(["approved", "rejected"] as const).map((c) => (
            <button key={c} type="button" role="radio" className="segment" aria-checked={choice === c}
              aria-selected={choice === c} onClick={() => setChoice(c)}>{c === "approved" ? "Approve" : "Reject"}</button>
          ))}
        </div>
      </section>
      <div className="group">
        <textarea className="textarea" rows={2} maxLength={500} value={note} placeholder="Why you're changing it (optional)"
          aria-label="Note (optional)" onChange={(e) => setNote(e.target.value)} />
      </div>
      {error && <p className="error-text" role="alert">{error}</p>}
      <Button disabled={busy} onClick={save}>
        {choice === current ? `Confirm: ${choice === "approved" ? "Approved" : "Rejected"}` : `Change to ${choice === "approved" ? "Approved" : "Rejected"}`}
      </Button>
    </div>
  );
}

export function MdApprovals() {
  const { me } = useSession();
  const wide = useWide();
  const [data, setData] = useState<Data | null>(null);
  const [tab, setTab] = useState<"waiting" | "decided">("waiting");
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try { setData(await getApprovals()); setError(null); refreshBadge(); } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    }
  }, []);
  useEffect(() => { void load(); }, [load]);
  if (!me?.user || me.user.role !== "md") return <Navigate to="/md/login" replace />;

  const fromManager = data?.waiting.filter((r) => r.role === "manager") || [];
  const fromWorkers = data?.waiting.filter((r) => r.role !== "manager") || [];
  const sel = data?.decided.find((r) => r.id === selected) || null;

  const tabs = (
    <div className="segmented" role="tablist" style={{ width: 280 }}>
      <button type="button" role="tab" className="segment" aria-selected={tab === "waiting"} onClick={() => setTab("waiting")}>
        Waiting{data ? ` · ${data.waiting.length}` : ""}</button>
      <button type="button" role="tab" className="segment" aria-selected={tab === "decided"} onClick={() => setTab("decided")}>Decided</button>
    </div>
  );

  return (
    <MdShell title="Approvals" actions={tabs}
      phoneToolbar={<div className="segmented" role="tablist">
        <button type="button" role="tab" className="segment" aria-selected={tab === "waiting"} onClick={() => setTab("waiting")}>
          Waiting{data ? ` · ${data.waiting.length}` : ""}</button>
        <button type="button" role="tab" className="segment" aria-selected={tab === "decided"} onClick={() => setTab("decided")}>Decided</button>
      </div>}>
      {error && <p className="error-text" role="alert">{error}</p>}
      {data && tab === "waiting" && (
        <div className="md-cards">
          {[["Waiting · from your manager", fromManager], ["Waiting · workers", fromWorkers]].map(([title, list]) =>
            (list as Reason[]).length > 0 && (
              <section key={title as string} className="stack-16" style={{ gap: 8 }}>
                <h2 className="group-title">{title as string}</h2>
                {(list as Reason[]).map((r) => <ReasonCard key={r.id} r={r} onDecided={() => void load()} />)}
              </section>
            ))}
          {data.waiting.length === 0 && <div className="group"><p className="empty-note">Nothing waiting.</p></div>}
        </div>
      )}
      {data && tab === "decided" && (
        <div className={wide ? "md-split" : ""}>
          <div className="group">
            {wide && (
              <div className="md-table-head md-decided-cols"><span>Name</span><span>Reason</span><span>Decision</span><span /></div>
            )}
            {data.decided.length === 0 && <p className="empty-note">Nothing decided yet.</p>}
            {data.decided.map((r) => wide ? (
              <div key={r.id} className={`md-table-row md-decided-cols${selected === r.id ? " md-row-selected" : ""}`}>
                <span className="two-line"><span style={{ fontWeight: 600 }}>{r.name}</span><span className="status-note">{r.day_label}</span></span>
                <span className="two-line"><span>{r.type_label}{r.detail ? ` · ${r.detail}` : ""}</span>
                  <span className="sub-note">{decisionLine(r.decisions[r.decisions.length - 1])}</span></span>
                <span><StatePill state={r.state} /></span>
                <Button variant="plain" onClick={() => setSelected(r.id)}>Override</Button>
              </div>
            ) : (
              <button key={r.id} type="button" className="row row-button" onClick={() => setSelected(r.id)}>
                <span className="row-body">
                  <span className="two-line"><span style={{ fontWeight: 600 }}>{r.name}</span>
                    <span className="status-note">{r.type_label} · {r.day_label}</span></span>
                  <span className="row-right"><StatePill state={r.state} />
                    <span style={{ color: "var(--text-4)", display: "flex" }}><ChevronRight /></span></span>
                </span>
              </button>
            ))}
          </div>
          {wide && (
            <aside>
              {sel ? <OverridePanel r={sel} onSaved={() => void load()} />
                : <div className="group"><p className="empty-note">Choose a decision to override it.</p></div>}
            </aside>
          )}
        </div>
      )}
      {!wide && sel && (
        <Sheet title="Override" cancelLabel="Close" onCancel={() => setSelected(null)}>
          <div className="sheet-body"><OverridePanel r={sel} onSaved={() => { setSelected(null); void load(); }} /></div>
        </Sheet>
      )}
    </MdShell>
  );
}

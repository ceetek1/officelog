// Add (or edit) a reason: a sheet with Cancel / Send.
import { useState } from "react";
import { ApiError, editReason, sendReason, type Reason, type ReasonType } from "../../api";
import { Group } from "../../ui/Grouped";
import { Sheet } from "../../ui/Sheets";

const TYPES: { id: ReasonType; label: string }[] = [
  { id: "late", label: "Late" }, { id: "absent", label: "Absent" },
  { id: "left_early", label: "Left early" }, { id: "missed_clock_out", label: "Missed clock-out" },
];

function CheckMark({ on }: { on: boolean }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
      style={{ color: "var(--primary)", visibility: on ? "visible" : "hidden" }}>
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </svg>
  );
}

/** The last 8 days (today and 7 before), as ISO dates with labels. */
function recentDays(today: string): { iso: string; label: string }[] {
  const out = [];
  const base = new Date(today + "T12:00:00Z");
  for (let i = 0; i <= 7; i++) {
    const d = new Date(base.getTime() - i * 86400000);
    const iso = d.toISOString().slice(0, 10);
    const label = (i === 0 ? "Today, " : i === 1 ? "Yesterday, " : d.toLocaleDateString("en-GB", { weekday: "short", timeZone: "UTC" }) + " ")
      + d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
    out.push({ iso, label });
  }
  return out;
}

export function AddReason({ today, date, type, editing, onDone, onCancel }: {
  today: string; date?: string; type?: ReasonType; editing?: Reason;
  onDone: () => void; onCancel: () => void;
}) {
  const [day, setDay] = useState(editing?.work_date || date || today);
  const [kind, setKind] = useState<ReasonType>(editing?.type || type || "late");
  const [text, setText] = useState(editing?.text || "");
  const [time, setTime] = useState(editing?.claimed_time || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const days = recentDays(today);
  const canSend = text.trim().length > 0 && (kind !== "missed_clock_out" || /^\d\d:\d\d$/.test(time)) && !busy;

  async function send() {
    if (!canSend) return;
    setBusy(true);
    setError(null);
    try {
      if (editing) await editReason(editing.id, text.trim(), kind === "missed_clock_out" ? time : null);
      else await sendReason(day, kind, text.trim(), kind === "missed_clock_out" ? time : undefined);
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet title={editing ? "Edit Reason" : "Add Reason"} onCancel={onCancel}
      right={<button type="button" className="btn btn-plain" style={{ fontWeight: 600 }} disabled={!canSend} onClick={send}>
        {busy ? "Sending…" : "Send"}</button>}>
      <div className="sheet-body">
        <Group>
          <label className="row">
            <span className="row-body">
              <span>Day</span>
              {editing ? <span className="row-value">{editing.day_label}</span> : (
                <select className="row-select" value={day} onChange={(e) => setDay(e.target.value)} aria-label="Day">
                  {days.map((d) => <option key={d.iso} value={d.iso}>{d.label}</option>)}
                </select>
              )}
            </span>
          </label>
        </Group>
        <Group title="What happened?">
          <div role="radiogroup" aria-label="What happened?">
            {TYPES.map((t) => (
              <button key={t.id} type="button" role="radio" aria-checked={kind === t.id} className="row row-button"
                disabled={!!editing} onClick={() => setKind(t.id)}>
                <span className="row-body"><span>{t.label}</span><CheckMark on={kind === t.id} /></span>
              </button>
            ))}
          </div>
        </Group>
        {kind === "missed_clock_out" && (
          <Group footer="When you actually left. Your manager checks it.">
            <label className="row">
              <span className="row-body">
                <span>Time you left</span>
                <input type="time" className="row-input mono" style={{ textAlign: "right", maxWidth: 140 }}
                  value={time} onChange={(e) => setTime(e.target.value)} />
              </span>
            </label>
          </Group>
        )}
        <Group title="Reason" footer={`${text.length} / 500`}>
          <textarea className="textarea" rows={4} maxLength={500} value={text}
            placeholder="What happened? Keep it short." onChange={(e) => setText(e.target.value)} aria-label="Reason" />
        </Group>
        {error && <p className="error-text" role="alert">{error}</p>}
      </div>
    </Sheet>
  );
}

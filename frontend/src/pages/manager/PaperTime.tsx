// Time from Paper (Prototype B "Time from paper"; decision D3). The manager or the MD adds a
// clock-in and/or clock-out from the paper sheet and says why. It can't be edited afterwards.
import { useEffect, useState } from "react";
import { ApiError, addPaperTime, getPaperDay, type PaperDay, type PaperReason } from "../../api";
import { Alert } from "../../ui/Alert";
import { Group } from "../../ui/Grouped";
import { CheckIcon } from "../../ui/icons";
import { Sheet } from "../../ui/Sheets";

export const PaperSheetIcon = () => (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 3h9l4 4v14H6z" /><path d="M14 3v5h5M9 12h7M9 16h7" /></svg>
);

function TimeRow({ label, recorded, value, onChange }: {
  label: string; recorded: PaperDay["people"][number]["clock_in"]; value: string; onChange: (v: string) => void;
}) {
  return (
    <label className="row">
      <span className="row-body">
        <span>{label}</span>
        {recorded ? (
          <span className="two-line" style={{ alignItems: "flex-end" }}>
            <span className="recorded">{recorded.time}</span>
            <span className="sub-note">{recorded.source === "paper" ? `From paper, ${recorded.entered_by}` : "Already recorded"}</span>
          </span>
        ) : (
          <input type="time" className="time-input" value={value} onChange={(e) => onChange(e.target.value)}
            aria-label={`${label} time`} />
        )}
      </span>
    </label>
  );
}

export function PaperTimeSheet({ onClose, onSaved, preselect }: {
  onClose: () => void; onSaved: (message: string) => void; preselect?: number;
}) {
  const [day, setDay] = useState<PaperDay | null>(null);
  const [date, setDate] = useState<string | undefined>(undefined);
  const [person, setPerson] = useState<number | null>(preselect ?? null);
  const [tin, setTin] = useState("");
  const [tout, setTout] = useState("");
  const [why, setWhy] = useState<PaperReason | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    getPaperDay(date).then((d) => { if (alive) { setDay(d); setError(null); } })
      .catch((e) => alive && setError(e instanceof Error ? e.message : "Something went wrong."));
    return () => { alive = false; };
  }, [date]);

  const who = day?.people.find((p) => p.user_id === person) || null;
  const newIn = who && !who.clock_in ? tin : "";
  const newOut = who && !who.clock_out ? tout : "";
  const ready = !!who && !!why && (!!newIn || !!newOut) && !busy;
  const done = !!who && !!who.clock_in && !!who.clock_out;

  async function save() {
    if (!ready || !who || !why || !day) return;
    setBusy(true);
    setError(null);
    try {
      const r = await addPaperTime(who.user_id, day.date, newIn || null, newOut || null, why);
      const times = r.added.map((a) => `${a.kind === "in" ? "clock-in" : "clock-out"} ${a.time}`).join(" and ");
      onSaved(`Added ${times} for ${r.name}.`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
    } finally { setBusy(false); }
  }

  return (
    <Sheet title="Time from Paper" onCancel={onClose}
      right={<button type="button" className="btn btn-plain" style={{ fontWeight: 600 }} disabled={!ready}
        onClick={() => void save()}>{busy ? "Saving…" : "Save"}</button>}>
      <div className="sheet-body">
        {!day && !error && <p className="status-note" aria-busy="true">Loading…</p>}
        {day && (
          <>
            <Group>
              <label className="row">
                <span className="row-body">
                  <span>Person</span>
                  <select className="row-select" aria-label="Person" value={person ?? ""} onChange={(e) => setPerson(e.target.value ? Number(e.target.value) : null)}>
                    <option value="">Choose</option>
                    {day.people.map((p) => <option key={p.user_id} value={p.user_id}>{p.name}{p.is_me ? " (you)" : ""}</option>)}
                  </select>
                </span>
              </label>
              <label className="row">
                <span className="row-body">
                  <span>Day</span>
                  <select className="row-select" aria-label="Day" value={day.date} onChange={(e) => setDate(e.target.value)}>
                    {day.days.map((d) => <option key={d.date} value={d.date}>{d.label}</option>)}
                  </select>
                </span>
              </label>
            </Group>
            {who && (
              <Group footer={done ? `${who.name} already has both times on this day. Recorded times can't be changed.` : undefined}>
                <TimeRow label="Clock in" recorded={who.clock_in} value={tin} onChange={setTin} />
                <TimeRow label="Clock out" recorded={who.clock_out} value={tout} onChange={setTout} />
              </Group>
            )}
            <section>
              <h2 className="group-title" id="why-paper">Why paper?</h2>
              <div className="group" role="radiogroup" aria-labelledby="why-paper">
                {day.reasons.map((r) => (
                  <button key={r.value} type="button" role="radio" aria-checked={why === r.value} aria-label={r.label}
                    className="row radio-row" onClick={() => setWhy(r.value)}>
                    <span className="row-body">
                      <span>{r.label}</span>
                      <span className="radio-check"><CheckIcon size={22} /></span>
                    </span>
                  </button>
                ))}
              </div>
              <p className="group-footer">It can't be changed later. The MD sees it in the activity log.</p>
            </section>
          </>
        )}
      </div>
      {error && <Alert title="Can't Add This Time" message={error} actions={[{ label: "OK", onPress: () => setError(null) }]} />}
    </Sheet>
  );
}

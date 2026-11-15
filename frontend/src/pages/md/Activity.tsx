// MD · Activity log (Prototype B). Everything important, newest first; append-only.
import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { getActivity, type ActivityEntry } from "../../api";
import { initials } from "../../format";
import { useSession } from "../../session";
import { Button } from "../../ui/Button";
import { Pill, type Tone } from "../../ui/Pill";
import { MdShell } from "./Shell";
import { PHONE, useMedia } from "../../ui/useMedia";

const FILTERS = [
  ["all", "All"], ["resets", "Phone resets"], ["decisions", "Decisions"], ["failed", "Failed sign-ins"],
  ["people", "People"], ["paper", "Paper"], ["tv", "TV"],
];

export function MdActivity() {
  const phone = useMedia(PHONE);
  const { me } = useSession();
  const [filter, setFilter] = useState("all");
  const [entries, setEntries] = useState<ActivityEntry[]>([]);
  const [more, setMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (append: boolean, f: string, before?: number) => {
    try {
      const r = await getActivity(f, before);
      setEntries((old) => (append ? old.concat(r.entries) : r.entries));
      setMore(r.more);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    }
  }, []);
  useEffect(() => { void load(false, filter); }, [filter, load]);
  if (!me?.user || me.user.role !== "md") return <Navigate to="/md/login" replace />;

  return (
    <MdShell title={phone ? "Activity" : "Activity log"}
      phoneActions={
        <select className="select-chip" aria-label="Show" value={filter} onChange={(e) => setFilter(e.target.value)}>
          {FILTERS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select>
      }>
      {!phone && <div className="md-filter-scroll">
        <div className="segmented" role="tablist" style={{ minWidth: 640, maxWidth: 900 }}>
          {FILTERS.map(([id, label]) => (
            <button key={id} type="button" role="tab" className="segment" aria-selected={filter === id}
              onClick={() => setFilter(id)}>{label}</button>
          ))}
        </div>
      </div>}
      {error && <p className="error-text" role="alert">{error}</p>}
      <div className="group">
        <div className="md-table-head md-activity-cols md-wide-only"><span>When</span><span>Who</span><span>Action</span><span>Details</span></div>
        {entries.length === 0 && <p className="empty-note">Nothing here yet.</p>}
        {entries.map((e) => (
          <div key={e.id} className="md-table-row md-activity-cols">
            <span className="status-note">{e.when}</span>
            <span className="md-who">
              {e.who !== "Admin command" && e.who !== "Unknown" && <span className="person-initials" aria-hidden="true">{initials(e.who)}</span>}
              {e.who}
            </span>
            <span><Pill tone={e.tone as Tone}>{e.label}</Pill></span>
            <span style={{ fontSize: 15, color: "#404040" }}>{e.details}</span>
          </div>
        ))}
      </div>
      {more && (
        <div style={{ maxWidth: 280 }}>
          <Button variant="secondary" onClick={() => void load(true, filter, entries[entries.length - 1]?.id)}>Load More</Button>
        </div>
      )}
    </MdShell>
  );
}

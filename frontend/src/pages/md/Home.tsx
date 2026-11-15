// MD · Today (Prototype B "MD · Today"; spec §10): the board for today or an earlier day, the
// manager's reasons waiting for the MD, and the entrance TV. The MD can add time from paper (D3).
import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { getApprovals, getMdToday, type MdToday, type Reason } from "../../api";
import { initials } from "../../format";
import { useSession } from "../../session";
import { Alert } from "../../ui/Alert";
import { Button } from "../../ui/Button";
import { MainPill } from "../../ui/DayPills";
import { Group, Row } from "../../ui/Grouped";
import { ChevronRight } from "../../ui/icons";
import { Pill } from "../../ui/Pill";
import { PHONE, useMedia } from "../../ui/useMedia";
import { ReasonCard } from "../manager/Approvals";
import { PaperSheetIcon, PaperTimeSheet } from "../manager/PaperTime";
import { MdShell } from "./Shell";

type Person = MdToday["people"][number];

function Status({ p }: { p: Person }) {
  if (p.status === "late" && !p.missing_clock_out) return <Pill tone="warn">Late · {p.late_minutes} min</Pill>;
  return <MainPill d={p} />;
}

const times = (p: Person) => <span className="mono">{p.clock_in?.time || "--:--"}</span>;

export function MdHome() {
  const { me } = useSession();
  const phone = useMedia(PHONE);
  const [params, setParams] = useSearchParams();
  const date = params.get("date") || undefined;
  const [data, setData] = useState<MdToday | null>(null);
  const [waiting, setWaiting] = useState<Reason[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [paper, setPaper] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [t, a] = await Promise.all([getMdToday(date), getApprovals()]);
      setData(t);
      setWaiting(a.waiting);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    }
  }, [date]);
  useEffect(() => {
    void load();
    const id = setInterval(() => { if (document.visibilityState === "visible") void load(); }, 30_000);
    return () => clearInterval(id);
  }, [load]);

  if (!me?.user || me.user.role !== "md") return <Navigate to="/md/login" replace />;

  const today = new Date().toLocaleDateString("en-CA", { timeZone: "Africa/Lagos" });
  const c = data?.counts;
  const fourth = data && !data.is_today
    ? { label: "Absent", value: c!.absent, color: c!.absent ? "var(--bad-fg)" : undefined }
    : { label: "Reasons waiting", value: waiting.length };
  const person = (p: Person) => `/md/people/${p.user_id}`;

  const team = data && (
    <section>
      <h2 className="group-title">Team</h2>
      {phone ? (
        <div className="group">
          {data.people.map((p) => (
            <Link key={p.user_id} to={person(p)} className="row row-link" style={{ minHeight: 56 }}>
              <span className="person-initials" aria-hidden="true">{initials(p.name)}</span>
              <span className="row-body">
                <span style={{ fontWeight: 600 }}>{p.name}</span>
                <span className="row-right">{times(p)}<Status p={p} /><span className="row-chevron"><ChevronRight /></span></span>
              </span>
            </Link>
          ))}
          {!data.people.length && <p className="empty-note">Nobody added yet.</p>}
        </div>
      ) : (
        <div className="group">
          <div className="md-table-head md-today-cols"><span>Name</span><span>In</span><span>Out</span><span>Status</span><span /></div>
          {data.people.map((p) => (
            <Link key={p.user_id} to={person(p)} className="md-table-row md-today-cols" aria-label={`${p.name}, history`}>
              <span className="md-who"><span className="person-initials" aria-hidden="true">{initials(p.name)}</span>{p.name}</span>
              {times(p)}
              <span className="mono">{p.clock_out?.time || "--:--"}</span>
              <span><Status p={p} /></span>
              <span className="row-chevron"><ChevronRight /></span>
            </Link>
          ))}
          {!data.people.length && <p className="empty-note">Nobody added yet.</p>}
        </div>
      )}
      {data.people.some((p) => p.clock_in?.source === "paper" || p.clock_out?.source === "paper") && (
        <p className="group-footer">Some times were added from the paper sheet; open a person to see who added them.</p>
      )}
    </section>
  );

  const side = data && (
    <div className="md-side">
      {waiting.length > 0 && (
        <section className="stack-16" style={{ gap: 8 }}>
          <h2 className="group-title" style={{ marginBottom: 0 }}>Waiting for you</h2>
          {waiting.map((r) => <ReasonCard key={r.id} r={r} onDecided={() => void load()} />)}
        </section>
      )}
      <Group title="Entrance TV">
        <Row label="Status" value={data.tv ? <Pill tone={data.tv.status === "online" ? "ok" : "bad"}>{data.tv.label}</Pill>
          : <Pill tone="wait">Not set up</Pill>} />
        {data.tv && <Row label="Last seen" value={data.tv.last_seen || "Never"} />}
        {data.tv && <Row label="Scans today" value={String(data.tv.scans_today)} />}
      </Group>
    </div>
  );

  return (
    <MdShell title={data && !data.is_today ? data.short_date : "Today"}
      eyebrow={data ? `${data.date} · ${data.active_people} active people` : undefined}
      actions={
        <div className="range-row">
          <label><span className="visually-hidden">Day</span>
            <input type="date" className="md-chip-input" max={today} value={data?.work_date || date || today}
              onChange={(e) => setParams(e.target.value && e.target.value !== today ? { date: e.target.value } : {})} />
          </label>
          <Button variant="secondary" style={{ width: "auto" }} onClick={() => setPaper(true)}>
            <PaperSheetIcon /><span>Time from Paper</span>
          </Button>
        </div>
      }>
      {error && <div className="stack-16"><p className="error-text" role="alert">{error}</p>
        <Button variant="secondary" style={{ width: "auto", alignSelf: "center" }} onClick={() => void load()}>Try Again</Button></div>}
      {data && (
        <>
          {!data.working_day && <p className="status-note">Not a working day. Scans are still recorded.</p>}
          <div className="stats stats-4">
            {[{ label: "On time", value: c!.on_time, color: "var(--ok-fg)" },
              { label: "Late", value: c!.late, color: "var(--warn-fg)" },
              data.is_today ? { label: "Not in yet", value: c!.not_in_yet } : { label: "Excused", value: c!.excused, color: "var(--excused-fg)" },
              fourth].map((s) => (
              <div key={s.label} className="stat">
                <span className="stat-label">{s.label}</span>
                <span className="stat-value" style={s.color ? { color: s.color } : undefined}>{s.value}</span>
              </div>
            ))}
          </div>
          {phone ? <>{side}{team}</> : <div className="md-split">{team}{side}</div>}
        </>
      )}
      {paper && <PaperTimeSheet onClose={() => setPaper(false)}
        onSaved={(m) => { setPaper(false); setSaved(m); void load(); }} />}
      {saved && <Alert title="Time Added" message={saved} actions={[{ label: "OK", onPress: () => setSaved(null) }]} />}
    </MdShell>
  );
}

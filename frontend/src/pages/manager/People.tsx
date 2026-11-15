// Manager · People (Prototype B "People", "Add person"; spec §4.4).
// Add a worker (invite link + QR), reset a lost phone, deactivate. The entrance TV is a row here.
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  addPerson, ApiError, deactivatePerson, getPeople, getTvs, resetPhone,
  type Invite, type Person, type Tv,
} from "../../api";
import { firstName, initials } from "../../format";
import { Alert } from "../../ui/Alert";
import { Button } from "../../ui/Button";
import { FieldRow, Group } from "../../ui/Grouped";
import { ChevronRight } from "../../ui/icons";
import { Pill, type Tone } from "../../ui/Pill";
import { ActionSheet, Sheet } from "../../ui/Sheets";
import { TabBar } from "../../ui/TabBar";
import { InviteCard } from "./InviteCard";

const TONE: Record<Person["status"], Tone> = { active: "ok", invited: "info", expired: "warn", off: "wait" };
export const TV_TONE: Record<Tv["status"], Tone> = { online: "ok", offline: "bad", waiting: "wait" };

export const PlusIcon = () => (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
);
const TvIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="2.5" y="4" width="19" height="13" rx="2" /><path d="M8 21h8M12 17v4" /></svg>
);

type Confirm = { kind: "reset" | "deactivate"; person: Person };

function AddPersonSheet({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [invite, setInvite] = useState<Invite | null>(null);

  async function create(e?: React.FormEvent) {
    e?.preventDefault();
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try { setInvite(await addPerson(name)); } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally { setBusy(false); }
  }

  return (
    <Sheet title="Add Person" onCancel={onClose} cancelLabel={invite ? "Close" : "Cancel"}
      right={invite
        ? <button type="button" className="btn btn-plain" style={{ fontWeight: 600 }} onClick={onClose}>Done</button>
        : <button type="button" className="btn btn-plain" style={{ fontWeight: 600 }} disabled={!name.trim() || busy}
            onClick={() => void create()}>Add</button>}>
      <div className="sheet-body">
        {!invite ? (
          <form onSubmit={create} className="stack-16">
            <Group footer="They get a one-time link to set up Face ID on their own phone. It works for 48 hours.">
              <FieldRow label="Name" type="text" autoComplete="off" autoCapitalize="words" maxLength={100}
                value={name} onChange={(e) => setName(e.target.value)} autoFocus placeholder="Full name" />
            </Group>
            {error && <p className="error-text" role="alert">{error}</p>}
            <Button type="submit" disabled={!name.trim() || busy}>{busy ? "Adding…" : "Add and Make Invite"}</Button>
          </form>
        ) : (
          <InviteCard invite={invite} />
        )}
      </div>
    </Sheet>
  );
}

function NewInviteSheet({ invite, hadPhone, onClose }: { invite: Invite; hadPhone: boolean; onClose: () => void }) {
  return (
    <Sheet title={hadPhone ? "New Phone" : "New Invite"} onCancel={onClose} cancelLabel="Close"
      right={<button type="button" className="btn btn-plain" style={{ fontWeight: 600 }} onClick={onClose}>Done</button>}>
      <div className="sheet-body">
        <InviteCard invite={invite} note={hadPhone
          ? `${firstName(invite.name)}'s old phone is signed out. They open this on the new phone to set up Face ID.`
          : `The old invite no longer works. ${firstName(invite.name)} opens this one on their own phone.`} />
      </div>
    </Sheet>
  );
}

export function People() {
  const [people, setPeople] = useState<Person[] | null>(null);
  const [count, setCount] = useState(0);
  const [tv, setTv] = useState<Tv | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [open, setOpen] = useState<Person | null>(null);
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const [invite, setInvite] = useState<{ invite: Invite; hadPhone: boolean } | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [p, t] = await Promise.all([getPeople(), getTvs()]);
      setPeople(p.people);
      setCount(p.active_count);
      setTv(t.tvs.find((x) => x.status !== "waiting") || t.tvs[0] || null);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function run(c: Confirm) {
    setConfirm(null);
    try {
      if (c.kind === "reset") setInvite({ invite: await resetPhone(c.person.id), hadPhone: c.person.status === "active" });
      else await deactivatePerson(c.person.id);
    } catch (e) {
      setFailed(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
    }
    void load();
  }

  const first = (p: Person) => firstName(p.name);
  const sheetActions = (p: Person) => [
    p.status === "active"
      ? { label: "Reset Phone", onPress: () => { setOpen(null); setConfirm({ kind: "reset", person: p }); } }
      : { label: "New Invite Link", onPress: () => { setOpen(null); void run({ kind: "reset", person: p }); } },
    ...(p.role === "worker"
      ? [{ label: "Deactivate", destructive: true, onPress: () => { setOpen(null); setConfirm({ kind: "deactivate", person: p }); } }]
      : []),
  ];

  return (
    <div className="phone">
      <header className="phone-header">
        <div className="phone-header-top">
          <button type="button" className="header-icon" aria-label="Add person" onClick={() => setAdding(true)}><PlusIcon /></button>
        </div>
        <h1 className="large-title">People</h1>
      </header>
      <main className="phone-main">
        {error && (
          <div className="stack-16">
            <p className="error-text" role="alert">{error}</p>
            <Button variant="secondary" onClick={() => void load()}>Try Again</Button>
          </div>
        )}
        <div className="group">
          <Link to="/people/tv" className="row row-link">
            <span className="tile-icon"><TvIcon /></span>
            <span className="row-body">
              <span>Entrance TV</span>
              <span className="row-right">
                {tv === null && <Pill tone="wait">Not set up</Pill>}
                {tv && <Pill tone={TV_TONE[tv.status]}>{tv.label}</Pill>}
                <span className="row-chevron"><ChevronRight /></span>
              </span>
            </span>
          </Link>
        </div>
        {people && (
          <section>
            <h2 className="group-title">{count} {count === 1 ? "person" : "people"}</h2>
            <div className="group">
              {people.map((p) => {
                const canAct = !p.is_me && p.status !== "off";
                const body = (
                  <>
                    <span className="person-initials" aria-hidden="true">{initials(p.name)}</span>
                    <span className="row-body" style={{ minHeight: 56 }}>
                      <span className="two-line">
                        <span style={{ fontWeight: 600 }}>{p.name}</span>
                        {p.is_me && <span className="sub-note">You · manager</span>}
                        {p.status === "invited" && p.invite_expires && <span className="sub-note">Invite until {p.invite_expires}</span>}
                      </span>
                      <Pill tone={TONE[p.status]}>{p.label}</Pill>
                    </span>
                  </>
                );
                return canAct ? (
                  <button key={p.id} type="button" className="row row-button row-link" onClick={() => setOpen(p)}
                    aria-label={`${p.name}, ${p.label}. Options`}>{body}</button>
                ) : (
                  <div key={p.id} className="row">{body}</div>
                );
              })}
              {people.length === 0 && <p className="empty-note">Nobody yet. Tap + to add a person.</p>}
            </div>
            <p className="group-footer">Deactivated people can't sign in or clock in. Their history is kept.</p>
          </section>
        )}
      </main>
      <TabBar role="manager" />

      {open && (
        <ActionSheet title={open.name}
          message={open.status === "active" ? "Lost or new phone?" : open.status === "invited" ? "Invite not used yet"
            : open.label === "Expired" ? "Invite expired" : "No phone set up yet"}
          actions={sheetActions(open)} onCancel={() => setOpen(null)} />
      )}
      {confirm?.kind === "reset" && (
        <Alert title={`Reset ${first(confirm.person)}'s phone?`}
          message="Their current phone stops working now. You'll get a new invite link for their new phone. The MD sees this in the activity log."
          actions={[{ label: "Cancel", cancel: true, onPress: () => setConfirm(null) },
                    { label: "Reset", bold: true, destructive: true, onPress: () => void run(confirm) }]} />
      )}
      {confirm?.kind === "deactivate" && (
        <Alert title={`Deactivate ${first(confirm.person)}?`}
          message="They can't sign in or clock in any more. Their history is kept."
          actions={[{ label: "Cancel", cancel: true, onPress: () => setConfirm(null) },
                    { label: "Deactivate", bold: true, destructive: true, onPress: () => void run(confirm) }]} />
      )}
      {failed && <Alert title="Didn't Work" message={failed} actions={[{ label: "OK", onPress: () => setFailed(null) }]} />}
      {adding && <AddPersonSheet onClose={() => { setAdding(false); void load(); }} />}
      {invite && <NewInviteSheet invite={invite.invite} hadPhone={invite.hadPhone} onClose={() => setInvite(null)} />}
    </div>
  );
}

// MD · People: the manager. With no manager yet, "Add Manager" makes them and shows their one-time
// invite (QR code, link, Copy). Afterwards, "New Invite Link" is a phone reset for the manager.
import { useCallback, useEffect, useState } from "react";
import { addMdManager, ApiError, getMdManager, newManagerInvite, type Invite, type MdManager } from "../../api";
import { initials } from "../../format";
import { Alert } from "../../ui/Alert";
import { Button } from "../../ui/Button";
import { FieldRow, Group } from "../../ui/Grouped";
import { Pill, type Tone } from "../../ui/Pill";
import { Sheet } from "../../ui/Sheets";
import { InviteCard } from "../manager/InviteCard";

const TONE: Record<MdManager["status"], Tone> = { active: "ok", invited: "info", expired: "warn" };

function AddManagerSheet({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [invite, setInvite] = useState<Invite | null>(null);
  async function create(e?: React.FormEvent) {
    e?.preventDefault();
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try { setInvite(await addMdManager(name)); } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally { setBusy(false); }
  }
  return (
    <Sheet title="Add Manager" onCancel={onClose} cancelLabel={invite ? "Close" : "Cancel"}
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
          <InviteCard invite={invite} note="The manager scans this with their own phone's camera, or opens the link, and sets up Face ID." />
        )}
      </div>
    </Sheet>
  );
}

export function ManagerCard({ onChanged }: { onChanged?: () => void }) {
  const [manager, setManager] = useState<MdManager | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [invite, setInvite] = useState<Invite | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setManager((await getMdManager()).manager); setError(null); } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function reissue() {
    setConfirm(false);
    try { setInvite(await newManagerInvite()); } catch (e) {
      setFailed(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
    }
    void load();
    onChanged?.();
  }

  return (
    <section style={{ maxWidth: 760 }}>
      <h2 className="group-title">Manager</h2>
      {error && <p className="error-text" role="alert">{error}</p>}
      {manager === null && (
        <div className="card">
          <div className="two-line">
            <span style={{ fontWeight: 600 }}>No manager yet</span>
            <span className="status-note">Add the manager here. They get a one-time link to set up Face ID on their own phone.</span>
          </div>
          <Button style={{ alignSelf: "flex-start", width: "auto" }} onClick={() => setAdding(true)}>Add Manager</Button>
        </div>
      )}
      {manager && (
        <div className="card">
          <div className="card-head">
            <span className="person-initials" aria-hidden="true">{initials(manager.name)}</span>
            <span className="two-line" style={{ flexGrow: 1 }}>
              <span style={{ fontWeight: 600 }}>{manager.name}</span>
              <span className="status-note">
                {manager.status === "invited" && manager.invite_expires ? `Invite works until ${manager.invite_expires}`
                  : manager.status === "active" ? "Signs in with Face ID on their phone"
                  : "Make a new invite link so they can set up their phone"}
              </span>
            </span>
            <Pill tone={TONE[manager.status]}>{manager.label}</Pill>
          </div>
          <Button variant="secondary" style={{ alignSelf: "flex-start", width: "auto" }}
            onClick={() => (manager.status === "active" ? setConfirm(true) : void reissue())}>New Invite Link</Button>
        </div>
      )}
      {adding && <AddManagerSheet onClose={() => { setAdding(false); void load(); onChanged?.(); }} />}
      {confirm && manager && (
        <Alert title={`New invite for ${manager.name.split(" ")[0]}?`}
          message="Their current phone stops working now, as with a lost phone. You'll get a new invite link for their phone. This is recorded in the activity log."
          actions={[{ label: "Cancel", cancel: true, onPress: () => setConfirm(false) },
                    { label: "Make Link", bold: true, destructive: true, onPress: () => void reissue() }]} />
      )}
      {invite && (
        <Sheet title="New Invite" onCancel={() => setInvite(null)} cancelLabel="Close"
          right={<button type="button" className="btn btn-plain" style={{ fontWeight: 600 }} onClick={() => setInvite(null)}>Done</button>}>
          <div className="sheet-body">
            <InviteCard invite={invite} note="Any older invite no longer works. The manager opens this on their own phone and sets up Face ID." />
          </div>
        </Sheet>
      )}
      {failed && <Alert title="Didn't Work" message={failed} actions={[{ label: "OK", onPress: () => setFailed(null) }]} />}
    </section>
  );
}

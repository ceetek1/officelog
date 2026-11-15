// Spec §7 (Nigeria Data Protection Act 2023): what is collected, why, who sees it, how long, and
// who to contact. Shown before a phone is registered, and at /privacy for anyone.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getPrivacy } from "../../api";
import { ChevronLeft } from "../../ui/icons";
import { Sheet } from "../../ui/Sheets";

function usePrivacy(fallbackCompany = "") {
  const [p, setP] = useState({ company: fallbackCompany, contact: "" });
  useEffect(() => { getPrivacy().then(setP).catch(() => undefined); }, []);
  return p;
}

export function PrivacyText({ company, contact }: { company: string; contact: string }) {
  const who = company || "your employer";
  return (
    <div className="prose">
      <h3>What we collect</h3>
      <p>Your name, the times you clock in and out, a passkey that ties this app to your phone, and the
        internet address (IP) your phone used for each clock-in or clock-out. If you can't scan, the
        manager may add your time from the paper sheet; that is recorded with who added it and why.</p>
      <h3>What we don't collect</h3>
      <p>No location, no photos, no phone number. Face ID or fingerprint is checked by your phone; your
        face and fingerprint never leave it.</p>
      <h3>Why</h3>
      <p>To record attendance at {who} during a trial of this system, and to measure whether the system
        is easy to use (for example, how often a scan works the first time).</p>
      <h3>Who sees it</h3>
      <p>You see your own times. The manager and the managing director see everyone's. Nobody else, and
        it is not sold or shared.</p>
      <h3>How long we keep it</h3>
      <p>For the length of the trial. Then it is deleted, unless {who} decides to keep using the system,
        in which case you will be told.</p>
      <h3>Your rights and who to contact</h3>
      <p>You can ask to see what is held about you, to have a mistake corrected, or to have it deleted
        when the trial ends. {contact
          ? <>Contact: <strong>{contact}</strong>.</>
          : <>Ask your manager or the managing director.</>}</p>
    </div>
  );
}

/** The notice as a sheet, during sign-up. */
export function PrivacyNotice({ company, onClose }: { company: string; onClose: () => void }) {
  const p = usePrivacy(company);
  return (
    <Sheet title="Privacy" onCancel={onClose} cancelLabel="Close">
      <div className="sheet-body"><PrivacyText company={p.company || company} contact={p.contact} /></div>
    </Sheet>
  );
}

/** /privacy: the notice as a page anyone can open. */
export function PrivacyPage() {
  const navigate = useNavigate();
  const p = usePrivacy();
  return (
    <div className="phone">
      <div className="navbar">
        <button type="button" className="btn btn-plain" onClick={() => (window.history.length > 1 ? navigate(-1) : navigate("/"))}>
          <ChevronLeft />Back</button>
        <span />
      </div>
      <header className="phone-header" style={{ paddingTop: 0 }}>
        <h1 className="large-title">Privacy Notice</h1>
        <span className="status-note">{p.company ? `${p.company} attendance` : "Attendance"} · Nigeria Data Protection Act 2023</span>
      </header>
      <main className="phone-main" style={{ paddingBottom: 32 }}>
        <PrivacyText company={p.company} contact={p.contact} />
      </main>
    </div>
  );
}

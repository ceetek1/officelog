// Privacy (Nigeria Data Protection Act 2023, spec §7), cut to four short rows: what is recorded,
// what never is, who sees it, how long. Shown from one line on the Welcome screen, from the
// account menu, and at /privacy for anyone.
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
    <>
      <dl className="facts">
        <div><dt>Recorded</dt><dd>Your clock times, this phone, and its internet address</dd></div>
        <div><dt>Never recorded</dt><dd>Location, photos or your face</dd></div>
        <div><dt>Seen by</dt><dd>You, your manager and the MD</dd></div>
        <div><dt>Kept</dt><dd>Until the trial ends, then deleted</dd></div>
      </dl>
      <p className="group-footer" style={{ marginTop: 8 }}>
        Used only to record attendance at {who}. To see, fix or delete your data, {contact
          ? <>contact <strong>{contact}</strong></> : <>ask your manager</>}. Nigeria Data Protection Act 2023.
      </p>
    </>
  );
}

/** The notice as a sheet, during sign-up. */
export function PrivacyNotice({ company, onClose }: { company: string; onClose: () => void }) {
  const p = usePrivacy(company);
  return (
    <Sheet title="Privacy" onCancel={onClose} cancelLabel="Close">
      <div className="sheet-body"><div><PrivacyText company={p.company || company} contact={p.contact} /></div></div>
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
          <ChevronLeft size={22} />Back</button>
        <span />
      </div>
      <header className="phone-header" style={{ paddingTop: 0 }}>
        <h1 className="large-title">Privacy</h1>
      </header>
      <main className="phone-main" style={{ paddingBottom: 32 }}>
        <div><PrivacyText company={p.company} contact={p.contact} /></div>
      </main>
    </div>
  );
}

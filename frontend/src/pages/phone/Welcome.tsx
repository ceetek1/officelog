// Invite link (2026 redesign): Welcome with the two home-screen steps, then Face ID.
// No privacy step: one line under Continue says what is recorded and links to the four-row notice.
// Tapping Continue is the acknowledgement the server records (privacy_ack), so the line must stay
// visible next to the button.
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError, getInvite, inviteOptions, inviteRegister, type InviteInfo } from "../../api";
import { faceIdAvailable, faceIdRegister, FaceIdCancelled } from "../../faceid";
import { isIos, isStandalone } from "../../format";
import { useSession } from "../../session";
import { AppIcon } from "../../ui/AppIcon";
import { Button } from "../../ui/Button";
import { ChevronLeft, FaceIdIcon, ShareIcon } from "../../ui/icons";
import { PrivacyNotice } from "./PrivacyNotice";

const PlusSquare = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
    strokeLinejoin="round" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="4" /><path d="M12 8.5v7M8.5 12h7" /></svg>
);
const Dots = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <circle cx="12" cy="5" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="12" cy="19" r="2" /></svg>
);

export function Welcome() {
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const { setMe } = useSession();
  const [info, setInfo] = useState<InviteInfo | null>(null);
  const [invalid, setInvalid] = useState<string | null>(null);
  const [step, setStep] = useState<1 | 2>(1);
  const [showNotice, setShowNotice] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getInvite(token).then(setInfo).catch((e) =>
      setInvalid(e instanceof ApiError ? e.message : "Something went wrong. Try again."));
  }, [token]);

  async function turnOnFaceId() {
    setBusy(true);
    setError(null);
    try {
      const { challenge_id, options } = await inviteOptions(token);
      const credential = await faceIdRegister(options);
      setMe(await inviteRegister(token, challenge_id, credential));
      navigate("/", { replace: true });
    } catch (e) {
      if (e instanceof FaceIdCancelled) setError("Face ID was cancelled. Tap the button to try again.");
      else setError(e instanceof Error ? e.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (invalid) {
    return (
      <div className="phone">
        <div className="center-screen">
          <h1 style={{ fontSize: 28, fontWeight: 700 }}>Link Not Valid</h1>
          <p className="subtitle">{invalid}</p>
          <Button variant="secondary" onClick={() => navigate("/", { replace: true })}>Open the App</Button>
        </div>
      </div>
    );
  }
  if (!info) return <div className="phone" aria-busy="true" />;

  if (step === 2) {
    const can = faceIdAvailable();
    return (
      <div className="phone">
        <div className="navbar">
          <button type="button" className="btn btn-plain" onClick={() => setStep(1)}><ChevronLeft size={22} />Back</button>
        </div>
        <main className="center-screen" style={{ gap: 20 }}>
          <span style={{ color: "var(--brand)", display: "flex" }}><FaceIdIcon size={88} /></span>
          <div className="stack-16" style={{ gap: 8 }}>
            <h1 style={{ fontSize: 28, lineHeight: "34px", fontWeight: 700 }}>Turn On Face ID</h1>
            <p className="subtitle">You'll use it to clock in and out.</p>
          </div>
          {error && <p className="error-text" role="alert">{error}</p>}
        </main>
        <footer className="phone-footer" style={{ gap: 14 }}>
          <Button onClick={turnOnFaceId} disabled={busy || !can}>{busy ? "Setting Up…" : "Turn On Face ID"}</Button>
          {can ? <p className="fine-print">No Face ID? Your fingerprint or passcode works too.</p>
            : <p className="error-text" role="alert">This browser can't use Face ID. Open the link in Safari (iPhone) or Chrome (Android).</p>}
        </footer>
      </div>
    );
  }

  const ios = isIos();
  const who = info.invited_by ? `${info.invited_by.split(" ")[0]} added you` : "You've been added";
  return (
    <div className="phone">
      <main className="phone-main" style={{ paddingTop: 64, gap: 32 }}>
        <div className="stack-16" style={{ padding: "0 4px", alignItems: "flex-start" }}>
          <AppIcon size={72} />
          <div className="stack-16" style={{ gap: 6 }}>
            <h1 className="large-title">Welcome, {info.name.split(" ")[0]}</h1>
            <p className="subtitle">{who} to {info.company || "the attendance app"}.</p>
          </div>
        </div>
        {!isStandalone() && (
          <section>
            <h2 className="group-title">First, add it to your Home Screen</h2>
            <ol className="group" style={{ margin: 0, padding: 0, listStyle: "none" }}>
              <li className="list-row">
                <span className="step-icon">{ios ? <ShareIcon size={18} /> : <Dots />}</span>
                <span className="list-row-body">{ios ? <span>Tap <strong>Share</strong></span> : <span>Tap the <strong>⋮</strong> menu</span>}</span>
              </li>
              <li className="list-row">
                <span className="step-icon"><PlusSquare /></span>
                <span className="list-row-body">{ios ? <span>Tap <strong>Add to Home Screen</strong></span> : <span>Tap <strong>Install app</strong></span>}</span>
              </li>
            </ol>
            <p className="group-footer">Then open the app from its new icon.</p>
          </section>
        )}
      </main>
      <footer className="phone-footer" style={{ gap: 14 }}>
        <Button onClick={() => setStep(2)}>Continue</Button>
        <p className="fine-print">
          Only your clock times are recorded.{" "}
          <button type="button" className="text-link" onClick={() => setShowNotice(true)}>Privacy</button>
        </p>
      </footer>
      {showNotice && <PrivacyNotice company={info.company} onClose={() => setShowNotice(false)} />}
    </div>
  );
}

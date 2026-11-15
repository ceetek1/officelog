// Invite link: welcome, add to home screen, privacy (step 1 of 2), then turn on Face ID (step 2 of 2).
// Prototype B boards "1 · Welcome, home screen, privacy" and "2 · Turn on Face ID".
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError, getInvite, inviteOptions, inviteRegister, type InviteInfo } from "../../api";
import { faceIdAvailable, faceIdRegister, FaceIdCancelled } from "../../faceid";
import { isIos, isStandalone } from "../../format";
import { useSession } from "../../session";
import { Button } from "../../ui/Button";
import { Group, Row } from "../../ui/Grouped";
import { ChevronLeft, ChevronRight, FaceIdIcon, PhoneIcon, ShareIcon } from "../../ui/icons";
import { PrivacyNotice } from "./PrivacyNotice";

export function Welcome() {
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const { setMe } = useSession();
  const [info, setInfo] = useState<InviteInfo | null>(null);
  const [invalid, setInvalid] = useState<string | null>(null);
  const [step, setStep] = useState<1 | 2>(1);
  const [ack, setAck] = useState(false);
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
    return (
      <div className="phone">
        <div className="navbar">
          <button type="button" className="btn btn-plain" onClick={() => setStep(1)}><ChevronLeft />Back</button>
        </div>
        <main className="center-screen">
          <span className="eyebrow">Step 2 of 2</span>
          <span style={{ color: "var(--primary)", display: "flex", margin: "12px 0" }}><FaceIdIcon /></span>
          <h1 style={{ fontSize: 28, lineHeight: 1.2, fontWeight: 700 }}>Turn On Face ID</h1>
          <p className="subtitle" style={{ lineHeight: 1.4 }}>You'll use it each time you clock in or out.</p>
          <p className="status-note">No Face ID? Your phone will use your fingerprint or passcode.</p>
          {error && <p className="error-text" role="alert">{error}</p>}
        </main>
        <footer className="phone-footer">
          <Button onClick={turnOnFaceId} disabled={busy || !faceIdAvailable()}>
            {busy ? "Setting Up…" : "Use Face ID"}
          </Button>
          {!faceIdAvailable() && (
            <p className="error-text">This browser can't use Face ID. Open the link in Safari (iPhone) or Chrome (Android).</p>
          )}
        </footer>
      </div>
    );
  }

  const ios = isIos();
  const standalone = isStandalone();
  return (
    <div className="phone">
      <main className="phone-main">
        <div className="stack-16" style={{ gap: 8, padding: "16px 4px 0" }}>
          <span className="eyebrow">Step 1 of 2</span>
          <h1 className="large-title">Welcome, {info.name.split(" ")[0]}</h1>
          <p className="subtitle" style={{ lineHeight: 1.4 }}>
            {info.invited_by ? `${info.invited_by} added you` : "You've been added"}
            {info.company ? ` to ${info.company}.` : " to the attendance app."}
          </p>
        </div>
        {!standalone && (
          <Group title="First, Add to Home Screen"
            footer={ios ? "Then open the app from its new icon, and always use that icon." : "Then open the app from its new icon."}>
            <div className="row">
              <span style={{ display: "flex", alignItems: "center", marginRight: 12, color: "var(--primary)" }}><ShareIcon /></span>
              <span className="row-body"><span>iPhone</span><span className="row-value" style={{ fontSize: 15 }}>Share › Add to Home Screen</span></span>
            </div>
            <div className="row">
              <span style={{ display: "flex", alignItems: "center", marginRight: 12, color: "var(--primary)" }}><PhoneIcon /></span>
              <span className="row-body"><span>Android</span><span className="row-value" style={{ fontSize: 15 }}>⋮ › Install app</span></span>
            </div>
          </Group>
        )}
        <Group title="Privacy" footer="No location. No photos. Your face never leaves your phone.">
          <Row label="What we collect" value="Times, this phone" />
          <Row label="Who sees it" value="Manager, MD" />
          <Row label="How long" value="During the test" />
          <button type="button" className="row row-button" onClick={() => setShowNotice(true)}>
            <span className="row-body">
              <span style={{ color: "var(--primary)" }}>Full privacy notice</span>
              <span style={{ color: "var(--text-4)", display: "flex" }}><ChevronRight /></span>
            </span>
          </button>
        </Group>
      </main>
      <footer className="phone-footer">
        <div className="group">
          <div className="row" style={{ paddingRight: 16, alignItems: "center", justifyContent: "space-between", gap: 12 }}>
            <span id="ack-label">I've read the privacy notice</span>
            <button type="button" role="switch" aria-checked={ack} aria-labelledby="ack-label" className="switch"
              onClick={() => setAck(!ack)} />
          </div>
        </div>
        <Button disabled={!ack} onClick={() => setStep(2)}>Continue</Button>
      </footer>
      {showNotice && <PrivacyNotice company={info.company} onClose={() => setShowNotice(false)} />}
    </div>
  );
}

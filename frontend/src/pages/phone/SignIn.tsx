// Face ID sign-in on a registered phone. Prototype B board "3 · Face ID: phone not registered".
import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, passkeyLogin, passkeyOptions } from "../../api";
import { faceIdConfirm, FaceIdCancelled } from "../../faceid";
import { useSession } from "../../session";
import { Alert } from "../../ui/Alert";
import { AppIcon } from "../../ui/AppIcon";
import { Button } from "../../ui/Button";
import { FaceIdIcon } from "../../ui/icons";

export function PhoneSignIn() {
  const { me, setMe } = useSession();
  const [busy, setBusy] = useState(false);
  const [notRegistered, setNotRegistered] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function signIn() {
    setBusy(true);
    setError(null);
    try {
      const { challenge_id, options } = await passkeyOptions();
      const credential = await faceIdConfirm(options);
      setMe(await passkeyLogin(challenge_id, credential));
    } catch (e) {
      if (e instanceof ApiError && e.code === "phone_not_registered") setNotRegistered(true);
      else if (e instanceof FaceIdCancelled) {
        // The phone can't tell us whether the person cancelled or has no passkey for this app.
        setError("Face ID was cancelled. If this keeps happening, ask your manager to reset your phone.");
      }
      else setError(e instanceof Error ? e.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="phone">
      <main className="center-screen" style={{ justifyContent: "flex-start", paddingTop: 120 }}>
        <AppIcon size={80} />
        <span style={{ fontSize: 20, fontWeight: 700 }}>{me?.company ? `${me.company} attendance` : "Attendance"}</span>
      </main>
      <footer className="phone-footer">
        {error && <p className="error-text" role="alert">{error}</p>}
        <Button onClick={signIn} disabled={busy}>{busy ? "Signing In…" : "Sign In with Face ID"}</Button>
        <Link to="/md/login" className="btn btn-plain" style={{ alignSelf: "center" }}>MD sign in</Link>
      </footer>
      {notRegistered && (
        <Alert
          icon={<span style={{ color: "var(--text-4)", display: "flex", marginBottom: 6 }}><FaceIdIcon size={44} /></span>}
          title="Phone Not Registered"
          message="This phone isn't registered. Ask your manager to reset your phone."
          actions={[{ label: "Try Again", bold: true, onPress: () => setNotRegistered(false) }]}
        />
      )}
    </div>
  );
}

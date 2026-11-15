// MD sign in (Prototype B: "MD · Log in" on the web, "MD phone · Sign in" on a phone).
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ApiError, passwordLogin } from "../../api";
import { useSession } from "../../session";
import { Alert } from "../../ui/Alert";
import { AppIcon } from "../../ui/AppIcon";
import { Button } from "../../ui/Button";
import { FieldRow, Group } from "../../ui/Grouped";
import { MD_DEVICE_KEY } from "./Shell";

export function MdSignIn() {
  const { me, setMe } = useSession();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [forgot, setForgot] = useState(false);

  if (me?.user?.role === "md") return <Navigate to="/md" replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      setMe(await passwordLogin(email, password));
      navigate("/md", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="centered-page">
      <form className="narrow stack" onSubmit={submit} noValidate>
        <div className="stack-16" style={{ alignItems: "center", textAlign: "center", gap: 14 }}>
          <AppIcon />
          <h1 className="large-title">Sign In</h1>
          <p className="subtitle">{me?.company ? `${me.company} attendance` : "Attendance"}</p>
        </div>
        <Group>
          <FieldRow label="Email" type="email" name="email" autoComplete="username" inputMode="email"
            autoCapitalize="none" spellCheck={false} required value={email}
            onChange={(e) => setEmail(e.target.value)} />
          <FieldRow label="Password" type="password" name="password" autoComplete="current-password"
            required value={password} onChange={(e) => setPassword(e.target.value)} />
        </Group>
        {error && <p className="error-text" role="alert">{error}</p>}
        <Button type="submit" disabled={busy || !email || !password}>
          {busy ? "Signing In…" : "Sign In"}
        </Button>
        <Button variant="plain" style={{ alignSelf: "center" }} onClick={() => setForgot(true)}>
          Forgot Password?
        </Button>
        <Button variant="plain" style={{ alignSelf: "center", color: "var(--text-2)" }} onClick={() => {
          try { localStorage.removeItem(MD_DEVICE_KEY); } catch { /* private mode */ }
          navigate("/", { replace: true });
        }}>Not the MD? Sign in with Face ID</Button>
      </form>
      {forgot && (
        <Alert
          title="Forgot Password?"
          message="Ask the person who set up the app to give you a new password."
          actions={[{ label: "OK", bold: true, onPress: () => setForgot(false) }]}
        />
      )}
    </main>
  );
}

// Placeholder MD home for Step 1. The Today board, history, approvals, activity log and usage
// pages arrive in later steps (spec §11).
import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { logout } from "../../api";
import { useSession } from "../../session";
import { Button } from "../../ui/Button";
import { Group, Row } from "../../ui/Grouped";

export function MdHome() {
  const { me, refresh } = useSession();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  if (!me?.user || me.user.role !== "md") return <Navigate to="/md/login" replace />;

  async function signOut() {
    setBusy(true);
    try { await logout(); } finally {
      await refresh();
      navigate("/md/login", { replace: true });
    }
  }

  return (
    <main className="centered-page">
      <div className="narrow stack">
        <h1 className="large-title">Today</h1>
        <Group footer="The Today board, history, approvals, activity log and usage pages come in the next steps.">
          <Row label="Signed in as" value={me.user.name} />
          <Row label="Role" value="MD" />
        </Group>
        <Button variant="secondary" onClick={signOut} disabled={busy}>Sign Out</Button>
      </div>
    </main>
  );
}

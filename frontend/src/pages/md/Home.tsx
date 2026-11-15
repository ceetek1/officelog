// MD Today. The full Today board arrives in Step 6 (spec §11). The MD can already add time from
// the paper sheet (decision D3).
import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useSession } from "../../session";
import { Alert } from "../../ui/Alert";
import { Button } from "../../ui/Button";
import { Group, Row } from "../../ui/Grouped";
import { PaperSheetIcon, PaperTimeSheet } from "../manager/PaperTime";
import { MdShell } from "./Shell";

export function MdHome() {
  const { me } = useSession();
  const [paper, setPaper] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
  if (!me?.user || me.user.role !== "md") return <Navigate to="/md/login" replace />;
  return (
    <MdShell title="Today" actions={
      <Button variant="secondary" style={{ width: "auto" }} onClick={() => setPaper(true)}>
        <PaperSheetIcon /><span>Time from Paper</span>
      </Button>
    }>
      <div style={{ maxWidth: 520 }}>
        <Group footer="The Today board, people's history and the usage numbers come in Step 6.">
          <Row label="Signed in as" value={me.user.name} />
          <Row label="Role" value="MD" />
        </Group>
      </div>
      {paper && <PaperTimeSheet onClose={() => setPaper(false)} onSaved={(m) => { setPaper(false); setSaved(m); }} />}
      {saved && <Alert title="Time Added" message={saved} actions={[{ label: "OK", onPress: () => setSaved(null) }]} />}
    </MdShell>
  );
}

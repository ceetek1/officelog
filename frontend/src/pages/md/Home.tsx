// MD Today. The full Today board arrives in Step 6 (spec §11).
import { Navigate } from "react-router-dom";
import { useSession } from "../../session";
import { Group, Row } from "../../ui/Grouped";
import { MdShell } from "./Shell";

export function MdHome() {
  const { me } = useSession();
  if (!me?.user || me.user.role !== "md") return <Navigate to="/md/login" replace />;
  return (
    <MdShell title="Today">
      <div style={{ maxWidth: 520 }}>
        <Group footer="The Today board, people's history and the usage numbers come in Step 6.">
          <Row label="Signed in as" value={me.user.name} />
          <Row label="Role" value="MD" />
        </Group>
      </div>
    </MdShell>
  );
}

import { Navigate, Route, Routes } from "react-router-dom";
import { MdHome } from "./pages/md/Home";
import { MdSignIn } from "./pages/md/SignIn";
import { useSession } from "./session";
import { Button } from "./ui/Button";

function Loading() {
  return <main className="centered-page" aria-busy="true"><span className="visually-hidden">Loading</span></main>;
}

function Home() {
  const { me } = useSession();
  if (me?.user?.role === "md") return <Navigate to="/md" replace />;
  // Phone sign-in with Face ID (decision D1) arrives in Step 2.
  return <Navigate to="/md/login" replace />;
}

export function App() {
  const { me, error, refresh } = useSession();
  if (!me) {
    if (error) {
      return (
        <main className="centered-page">
          <div className="narrow stack" style={{ textAlign: "center" }}>
            <h1 className="large-title">Can't Connect</h1>
            <p className="subtitle">{error}</p>
            <Button onClick={() => void refresh()}>Try Again</Button>
          </div>
        </main>
      );
    }
    return <Loading />;
  }
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/md/login" element={<MdSignIn />} />
      <Route path="/md" element={<MdHome />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

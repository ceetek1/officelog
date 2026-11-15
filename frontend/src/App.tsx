import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { MdHome } from "./pages/md/Home";
import { MdSignIn } from "./pages/md/SignIn";
import { PhoneSignIn } from "./pages/phone/SignIn";
import { Welcome } from "./pages/phone/Welcome";
import { useSession } from "./session";
import { Button } from "./ui/Button";

// Loaded only where needed: the TV never downloads the camera scanner, phones never the TV board.
const Today = lazy(() => import("./pages/phone/Today").then((m) => ({ default: m.Today })));
const Tv = lazy(() => import("./pages/tv/Tv").then((m) => ({ default: m.Tv })));
const TvPair = lazy(() => import("./pages/tv/Tv").then((m) => ({ default: m.TvPair })));

function Loading() {
  return <main className="centered-page" aria-busy="true"><span className="visually-hidden">Loading</span></main>;
}

function Home() {
  const { me } = useSession();
  const role = me?.user?.role;
  if (role === "md") return <Navigate to="/md" replace />;
  if (role === "worker" || role === "manager") return <Today />;
  return <PhoneSignIn />;
}

export function App() {
  const { me, error, refresh } = useSession();
  const { pathname } = useLocation();
  // The TV doesn't use a user session; don't wait for one.
  if (pathname.startsWith("/tv")) {
    return (
      <Suspense fallback={null}>
        <Routes>
          <Route path="/tv" element={<Tv />} />
          <Route path="/tv/pair/:token" element={<TvPair />} />
        </Routes>
      </Suspense>
    );
  }
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
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/invite/:token" element={<Welcome />} />
        <Route path="/md/login" element={<MdSignIn />} />
        <Route path="/md" element={<MdHome />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

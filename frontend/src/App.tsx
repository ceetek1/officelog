import { lazy, Suspense, type JSX } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { MdHome } from "./pages/md/Home";
import { MD_DEVICE_KEY } from "./pages/md/Shell";
import { MdSignIn } from "./pages/md/SignIn";
import { PhoneSignIn } from "./pages/phone/SignIn";
import { Welcome } from "./pages/phone/Welcome";
import { useSession } from "./session";
import { Button } from "./ui/Button";

// Loaded only where needed: the TV never downloads the camera scanner, phones never the TV board.
const Today = lazy(() => import("./pages/phone/Today").then((m) => ({ default: m.Today })));
const History = lazy(() => import("./pages/phone/History").then((m) => ({ default: m.History })));
const Team = lazy(() => import("./pages/manager/Team").then((m) => ({ default: m.Team })));
const Reasons = lazy(() => import("./pages/phone/Reasons").then((m) => ({ default: m.Reasons })));
const MdApprovals = lazy(() => import("./pages/md/Approvals").then((m) => ({ default: m.MdApprovals })));
const MdActivity = lazy(() => import("./pages/md/Activity").then((m) => ({ default: m.MdActivity })));
const ManagerApprovals = lazy(() => import("./pages/manager/Approvals").then((m) => ({ default: m.Approvals })));
const People = lazy(() => import("./pages/manager/People").then((m) => ({ default: m.People })));
const TvSetup = lazy(() => import("./pages/manager/TvSetup").then((m) => ({ default: m.TvSetup })));
const MdPeople = lazy(() => import("./pages/md/People").then((m) => ({ default: m.MdPeople })));
const MdPersonHistory = lazy(() => import("./pages/md/Person").then((m) => ({ default: m.MdPersonHistory })));
const MdUsage = lazy(() => import("./pages/md/Usage").then((m) => ({ default: m.MdUsage })));
const PrivacyPage = lazy(() => import("./pages/phone/PrivacyNotice").then((m) => ({ default: m.PrivacyPage })));
const Tv = lazy(() => import("./pages/tv/Tv").then((m) => ({ default: m.Tv })));
const TvPair = lazy(() => import("./pages/tv/Tv").then((m) => ({ default: m.TvPair })));

function Loading() {
  return <main className="centered-page" aria-busy="true"><span className="visually-hidden">Loading</span></main>;
}

function Home() {
  const { me } = useSession();
  const role = me?.user?.role;
  if (role === "md") return <Navigate to="/md" replace />;
  if (role === "worker" || role === "manager") return <Today role={role} />;
  // The MD's home-screen app opens "/": if this phone was last used by the MD, go to email sign-in.
  let mdDevice = false;
  try { mdDevice = localStorage.getItem(MD_DEVICE_KEY) === "1"; } catch { /* private mode */ }
  if (mdDevice) return <Navigate to="/md/login" replace />;
  return <PhoneSignIn />;
}

/** A page for people who clock in; anyone else goes home. */
function ClocksIn({ children }: { children: (role: "worker" | "manager") => JSX.Element }) {
  const { me } = useSession();
  const role = me?.user?.role;
  return role === "worker" || role === "manager" ? children(role) : <Navigate to="/" replace />;
}

function ManagerOnly({ children }: { children: JSX.Element }) {
  const { me } = useSession();
  return me?.user?.role === "manager" ? children : <Navigate to="/" replace />;
}

function MdOnly({ children }: { children: JSX.Element }) {
  const { me } = useSession();
  return me?.user?.role === "md" ? children : <Navigate to="/md/login" replace />;
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
        <Route path="/history" element={<ClocksIn>{(role) => <History role={role} />}</ClocksIn>} />
        <Route path="/reasons" element={<ClocksIn>{(role) => <Reasons role={role} />}</ClocksIn>} />
        <Route path="/team" element={<ManagerOnly><Team /></ManagerOnly>} />
        <Route path="/approvals" element={<ManagerOnly><ManagerApprovals /></ManagerOnly>} />
        <Route path="/people" element={<ManagerOnly><People /></ManagerOnly>} />
        <Route path="/people/tv" element={<ManagerOnly><TvSetup /></ManagerOnly>} />
        <Route path="/invite/:token" element={<Welcome />} />
        <Route path="/md/login" element={<MdSignIn />} />
        <Route path="/md" element={<MdHome />} />
        <Route path="/md/approvals" element={<MdApprovals />} />
        <Route path="/md/activity" element={<MdActivity />} />
        <Route path="/md/people" element={<MdOnly><MdPeople /></MdOnly>} />
        <Route path="/md/people/:id" element={<MdOnly><MdPersonHistory /></MdOnly>} />
        <Route path="/md/usage" element={<MdOnly><MdUsage /></MdOnly>} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

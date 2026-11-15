// MD layout (Prototype B "MD · …" boards): top bar on wide screens, bottom tabs on phones.
import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { getApprovals, logout } from "../../api";
import { initials } from "../../format";
import { useSession } from "../../session";
import { ClockIcon } from "../../ui/icons";

const NAV = [
  { to: "/md", label: "Today" },
  { to: "/md/approvals", label: "Approvals" },
  { to: "/md/activity", label: "Activity log" },
];

export function MdShell({ title, actions, children }: { title: string; actions?: ReactNode; children: ReactNode }) {
  const { me, refresh } = useSession();
  const navigate = useNavigate();
  const [waiting, setWaiting] = useState(0);
  useEffect(() => { getApprovals().then((a) => setWaiting(a.waiting.length)).catch(() => undefined); }, []);
  const name = me?.user?.name || "";

  async function signOut() {
    try { await logout(); } finally { await refresh(); navigate("/md/login", { replace: true }); }
  }

  const links = NAV.map((n) => (
    <NavLink key={n.to} to={n.to} end className={({ isActive }) => `md-nav-link${isActive ? " md-nav-active" : ""}`}>
      {n.label}
      {n.to === "/md/approvals" && waiting > 0 && <span className="md-badge" aria-label={`${waiting} waiting`}>{waiting}</span>}
    </NavLink>
  ));
  return (
    <div className="md">
      <header className="md-top">
        <div className="md-top-inner">
          <span className="md-brand"><span className="md-brand-icon"><ClockIcon size={20} /></span>{me?.company || "Attendance"}</span>
          <nav aria-label="MD" className="md-nav md-nav-wide">{links}</nav>
          <span className="md-user">
            <span className="person-initials" aria-hidden="true" style={{ margin: 0 }}>{initials(name)}</span>
            <span className="md-user-name">{name}</span>
            <button type="button" className="btn btn-plain" style={{ fontWeight: 600 }} onClick={signOut}>Sign Out</button>
          </span>
        </div>
      </header>
      <main className="md-main">
        <div className="md-title-row">
          <h1 className="large-title">{title}</h1>
          {actions}
        </div>
        {children}
      </main>
      <nav aria-label="MD" className="md-nav md-nav-phone">{links}</nav>
    </div>
  );
}

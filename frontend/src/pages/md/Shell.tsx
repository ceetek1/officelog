// MD layout (Prototype B "MD · …" boards): top bar on wide screens, bottom tabs on phones.
import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { getApprovals, logout } from "../../api";
import { initials } from "../../format";
import { useSession } from "../../session";
import { ChevronLeft, ClockIcon } from "../../ui/icons";

// On phones the bottom bar has the same pages with short names (People holds "Add Manager").
const NAV = [
  { to: "/md", label: "Today", short: "Today" },
  { to: "/md/people", label: "People", short: "People" },
  { to: "/md/approvals", label: "Approvals", short: "Approvals" },
  { to: "/md/activity", label: "Activity log", short: "Activity" },
  { to: "/md/usage", label: "Usage", short: "Usage" },
];

export function MdShell({ title, actions, children, back, subtitle, eyebrow }: {
  title: string; actions?: ReactNode; children: ReactNode; back?: { to: string; label: string };
  subtitle?: string; eyebrow?: string;
}) {
  const { me, refresh } = useSession();
  const navigate = useNavigate();
  const [waiting, setWaiting] = useState(0);
  useEffect(() => { getApprovals().then((a) => setWaiting(a.waiting.length)).catch(() => undefined); }, []);
  const name = me?.user?.name || "";

  async function signOut() {
    try { await logout(); } finally { await refresh(); navigate("/md/login", { replace: true }); }
  }

  const links = (phone: boolean) => NAV.map((n) => (
    <NavLink key={n.to} to={n.to} end={n.to === "/md"}
      className={({ isActive }) => `md-nav-link${isActive ? " md-nav-active" : ""}`}>
      {phone ? n.short : n.label}
      {n.to === "/md/approvals" && waiting > 0 && <span className="md-badge" aria-label={`${waiting} waiting`}>{waiting}</span>}
    </NavLink>
  ));
  return (
    <div className="md">
      <header className="md-top">
        <div className="md-top-inner">
          <span className="md-brand"><span className="md-brand-icon"><ClockIcon size={20} /></span>{me?.company || "Attendance"}</span>
          <nav aria-label="MD" className="md-nav md-nav-wide">{links(false)}</nav>
          <span className="md-user">
            <span className="person-initials" aria-hidden="true" style={{ margin: 0 }}>{initials(name)}</span>
            <span className="md-user-name">{name}</span>
            <button type="button" className="btn btn-plain" style={{ fontWeight: 600 }} onClick={signOut}>Sign Out</button>
          </span>
        </div>
      </header>
      <main className="md-main">
        <div className="md-title-row">
          <div className="two-line" style={{ gap: 4 }}>
            {back && <Link to={back.to} className="md-back"><ChevronLeft size={24} />{back.label}</Link>}
            {eyebrow && <span className="eyebrow">{eyebrow}</span>}
            <h1 className="large-title">{title}</h1>
            {subtitle && <span className="subtitle">{subtitle}</span>}
          </div>
          {actions}
        </div>
        {children}
        <p className="md-footer"><Link to="/privacy">Privacy notice</Link></p>
      </main>
      <nav aria-label="MD" className="md-nav md-nav-phone">{links(true)}</nav>
    </div>
  );
}

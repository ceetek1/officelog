// MD layout. On a laptop: the web layout (Prototype B "MD · …" boards: top bar, wide tables).
// On a phone: app-style like the other phone screens (Prototype B "MD · phone" boards): a large title,
// an account button, and a bottom tab bar with icons (Today, Approvals, Activity, Usage). Detail
// pages (a person, People, the manager) get a back button instead of the large title.
import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { getApprovals, logout } from "../../api";
import { initials } from "../../format";
import { useSession } from "../../session";
import { ChevronLeft, ClockIcon } from "../../ui/icons";
import { ActionSheet } from "../../ui/Sheets";
import { TabBar } from "../../ui/TabBar";
import { PHONE, useMedia } from "../../ui/useMedia";

const NAV = [
  { to: "/md", label: "Today" },
  { to: "/md/people", label: "People" },
  { to: "/md/approvals", label: "Approvals" },
  { to: "/md/activity", label: "Activity log" },
  { to: "/md/usage", label: "Usage" },
];

/** Remembered so a signed-out MD who opens the home-screen app lands on email sign-in. */
export const MD_DEVICE_KEY = "att_md_device";

export function MdShell({ title, actions, phoneActions, phoneToolbar, children, back, subtitle, eyebrow }: {
  title: string;
  /** Laptop: shown at the right of the title. */
  actions?: ReactNode;
  /** Phone: small buttons at the top right, next to the account button. */
  phoneActions?: ReactNode;
  /** Phone: shown at the top of the page, under the title. */
  phoneToolbar?: ReactNode;
  children: ReactNode;
  back?: { to: string; label: string };
  subtitle?: string;
  eyebrow?: string;
}) {
  const { me, refresh } = useSession();
  const navigate = useNavigate();
  const phone = useMedia(PHONE);
  const [waiting, setWaiting] = useState(0);
  const [menu, setMenu] = useState(false);
  useEffect(() => {
    if (!phone) getApprovals().then((a) => setWaiting(a.waiting.length)).catch(() => undefined);
  }, [phone]);
  useEffect(() => { try { localStorage.setItem(MD_DEVICE_KEY, "1"); } catch { /* private mode */ } }, []);
  const name = me?.user?.name || "";

  async function signOut() {
    setMenu(false);
    try { await logout(); } finally { await refresh(); navigate("/md/login", { replace: true }); }
  }

  if (phone) {
    return (
      <div className="phone">
        {back ? (
          <div className="navbar">
            <button type="button" className="btn btn-plain" onClick={() => navigate(back.to)}><ChevronLeft />{back.label}</button>
            <span className="navbar-title">{title}</span>
            <span />
          </div>
        ) : (
          <header className="phone-header">
            <div className="phone-header-top" style={{ gap: 8 }}>
              {phoneActions}
              <button type="button" className="avatar" aria-label={`Account: ${name}`} onClick={() => setMenu(true)}>
                <span aria-hidden="true">{initials(name)}</span>
              </button>
            </div>
            {eyebrow && <span className="eyebrow">{eyebrow}</span>}
            <h1 className="large-title">{title}</h1>
          </header>
        )}
        <main className="phone-main" style={{ paddingBottom: 24 }}>
          {subtitle && <p className="status-note">{subtitle}</p>}
          {back && phoneActions}
          {phoneToolbar}
          {children}
        </main>
        <TabBar role="md" />
        {menu && (
          <ActionSheet title={name} message={me?.company ? `MD · ${me.company}` : "MD"} onCancel={() => setMenu(false)}
            actions={[{ label: "Privacy Notice", onPress: () => { setMenu(false); navigate("/privacy"); } },
                      { label: "Sign Out", destructive: true, onPress: () => void signOut() }]} />
        )}
      </div>
    );
  }

  return (
    <div className="md">
      <header className="md-top">
        <div className="md-top-inner">
          <span className="md-brand"><span className="md-brand-icon"><ClockIcon size={20} /></span>{me?.company || "Attendance"}</span>
          <nav aria-label="MD" className="md-nav md-nav-wide">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.to === "/md"}
                className={({ isActive }) => `md-nav-link${isActive ? " md-nav-active" : ""}`}>
                {n.label}
                {n.to === "/md/approvals" && waiting > 0 && <span className="md-badge" aria-label={`${waiting} waiting`}>{waiting}</span>}
              </NavLink>
            ))}
          </nav>
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
    </div>
  );
}

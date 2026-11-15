// iOS bottom tab bar. Workers: Today, History, Reasons. Manager: Me, Team, Approvals (People in Step 5).
import { useEffect, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { getApprovals, type Role } from "../api";
import { ClockIcon } from "./icons";

const Icon = ({ d }: { d: ReactNode }) => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{d}</svg>
);
const calendar = <Icon d={<><rect x="3.5" y="5" width="17" height="15" rx="2" /><path d="M3.5 10h17M8 3v4M16 3v4" /></>} />;
const bubble = <Icon d={<path d="M5 5h14v10H9l-4 4z" />} />;
const people = <Icon d={<><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0113 0M16 4.5a3.5 3.5 0 010 7M18 14a6.5 6.5 0 013.5 6" /></>} />;
const tray = <Icon d={<><path d="M4 13l2.5-8h11L20 13v6H4z" /><path d="M4 13h5a3 3 0 006 0h5" /></>} />;

// The manager's "waiting" badge, shared across tab bars and refreshed after decisions.
let badge = 0;
const listeners = new Set<(n: number) => void>();
export function refreshBadge() {
  getApprovals().then((a) => { badge = a.waiting.length; listeners.forEach((l) => l(badge)); }).catch(() => undefined);
}

export function TabBar({ role }: { role: Role }) {
  const [waiting, setWaiting] = useState(badge);
  useEffect(() => {
    if (role !== "manager") return;
    listeners.add(setWaiting);
    refreshBadge();
    return () => { listeners.delete(setWaiting); };
  }, [role]);

  const tabs = role === "manager"
    ? [{ to: "/", label: "Me", icon: <ClockIcon size={28} stroke={1.8} /> }, { to: "/team", label: "Team", icon: people },
       { to: "/approvals", label: "Approvals", icon: tray, badge: waiting }]
    : [{ to: "/", label: "Today", icon: <ClockIcon size={28} stroke={1.8} /> }, { to: "/history", label: "History", icon: calendar },
       { to: "/reasons", label: "Reasons", icon: bubble }];
  return (
    <nav className="tabbar" aria-label="Tabs">
      {tabs.map((t) => (
        <NavLink key={t.to} to={t.to} end className={({ isActive }) => `tab${isActive ? " tab-active" : ""}`}>
          {t.icon}<span>{t.label}</span>
          {"badge" in t && t.badge ? <span className="tab-badge" aria-label={`${t.badge} waiting`}>{t.badge}</span> : null}
        </NavLink>
      ))}
    </nav>
  );
}

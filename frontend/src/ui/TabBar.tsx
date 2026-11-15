// iOS bottom tab bar. Workers: Today, History. Manager: Me, Team (Approvals and People come later).
import { NavLink } from "react-router-dom";
import type { Role } from "../api";
import { ClockIcon } from "./icons";

function CalendarIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3.5" y="5" width="17" height="15" rx="2" /><path d="M3.5 10h17M8 3v4M16 3v4" />
    </svg>
  );
}

function PeopleIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0113 0M16 4.5a3.5 3.5 0 010 7M18 14a6.5 6.5 0 013.5 6" />
    </svg>
  );
}

export function TabBar({ role }: { role: Role }) {
  const tabs = role === "manager"
    ? [{ to: "/", label: "Me", icon: <ClockIcon size={28} stroke={1.8} /> }, { to: "/team", label: "Team", icon: <PeopleIcon /> }]
    : [{ to: "/", label: "Today", icon: <ClockIcon size={28} stroke={1.8} /> }, { to: "/history", label: "History", icon: <CalendarIcon /> }];
  return (
    <nav className="tabbar" aria-label="Tabs">
      {tabs.map((t) => (
        <NavLink key={t.to} to={t.to} end className={({ isActive }) => `tab${isActive ? " tab-active" : ""}`}>
          {t.icon}<span>{t.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

const NAV = [
  { to: "/submit", label: "Submit Ticket" },
  { to: "/patterns", label: "Recurring Patterns" },
];

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <div className="app-frame">
        <header className="topbar">
          <span className="topbar__brand">TicketIQ</span>
          <nav className="topbar__nav">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => (isActive ? "navlink is-active" : "navlink")}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </header>

        <main className="app-main">{children}</main>

        <footer className="footer">
          <span>© 2026 TicketIQ Intelligence Shell</span>
          <span>v4.2.0-stable</span>
        </footer>
      </div>
    </div>
  );
}

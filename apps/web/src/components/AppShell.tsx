import {
  Bot,
  Boxes,
  FlaskConical,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";
import { navigate } from "../router";

const navigation: Array<{ to: string; label: string; icon: LucideIcon }> = [
  { to: "/showcase", label: "Industry Cases", icon: Boxes },
  { to: "/fit", label: "AI Fit Analyzer", icon: FlaskConical },
  { to: "/ask", label: "Ask Studio", icon: Bot },
];

export default function AppShell({ pathname, children }: { pathname: string; children: ReactNode }) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div>
            <strong>Applied AI Studio</strong>
            <span>Applied AI workbench</span>
          </div>
        </div>

        <nav className="primary-nav" aria-label="Primary navigation">
          {navigation.map(({ to, label, icon: Icon }) => (
            <a
              key={to}
              href={to}
              className={pathname === to ? "nav-link active" : "nav-link"}
              aria-current={pathname === to ? "page" : undefined}
              onClick={(event) => {
                event.preventDefault();
                navigate(to);
              }}
            >
              <Icon size={18} aria-hidden="true" />
              <span>{label}</span>
            </a>
          ))}
        </nav>

        <div className="sidebar-status">
          <div className="status-line">
            <span className="status-dot" />
            Locally hosted
          </div>
          <div className="runtime-line">
            <Bot size={14} aria-hidden="true" />
            GitHub Copilot SDK
          </div>
          <small>Public synthetic data only</small>
        </div>
      </aside>
      <main className="main-surface">
        {children}
      </main>
    </div>
  );
}
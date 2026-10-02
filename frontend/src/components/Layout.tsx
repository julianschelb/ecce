import { useState } from "react";
import { NavLink, Outlet, useOutletContext } from "react-router-dom";
import { AboutDialog } from "@/components/AboutDialog";
import { useAuth } from "@/hooks/useAuth";

export interface LayoutContext {
  openAbout: () => void;
}

/** Access to the header's About dialog from routed pages. */
export function useLayoutContext(): LayoutContext {
  return useOutletContext<LayoutContext>();
}

export function Layout() {
  const { isAdmin } = useAuth();
  const [about, setAbout] = useState(false);
  const link = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-2.5 py-1 text-[13px] font-medium transition-colors ${isActive ? "bg-pop-soft text-ink" : "text-ink-2 hover:bg-line-soft hover:text-ink"}`;
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-gradient-to-b from-bg to-[#f2f1ec]">
        <div className="mx-auto flex h-12 max-w-[1600px] items-center justify-between px-4">
          <NavLink to="/" className="flex items-baseline gap-2">
            <span className="font-serif text-[19px] font-semibold tracking-tight text-ink">ECCE</span>
            <span className="hidden font-mono text-[11px] uppercase tracking-wider text-muted sm:inline">Entity-centric corpus exploration</span>
          </NavLink>
          <nav className="flex items-center gap-1">
            <NavLink to="/" end className={link}>
              Gallery
            </NavLink>
            <a href="/api/docs" className="rounded-md px-2.5 py-1 text-[13px] font-medium text-ink-2 hover:bg-line-soft hover:text-ink" target="_blank" rel="noreferrer">
              API
            </a>
            <button type="button" className="rounded-md px-2.5 py-1 text-[13px] font-medium text-ink-2 hover:bg-line-soft hover:text-ink" onClick={() => setAbout(true)}>
              About
            </button>
            <NavLink to="/admin" className={link} title="Administration">
              {isAdmin ? "Admin ●" : "Admin"}
            </NavLink>
            {/* server-rendered pages (legal notice under § 5 DDG, privacy policy under Art. 13 GDPR) */}
            <span className="ml-1 hidden h-4 border-l border-line sm:inline" aria-hidden />
            <a href="/legal" className="rounded-md px-2 py-1 text-[12px] text-muted hover:bg-line-soft hover:text-ink">
              Legal
            </a>
            <a href="/privacy" className="rounded-md px-2 py-1 text-[12px] text-muted hover:bg-line-soft hover:text-ink">
              Privacy
            </a>
            <NavLink to="/contact" className="rounded-md px-2 py-1 text-[12px] text-muted hover:bg-line-soft hover:text-ink">
              Contact
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="flex-1">
        <Outlet context={{ openAbout: () => setAbout(true) } satisfies LayoutContext} />
      </main>
      <AboutDialog open={about} onClose={() => setAbout(false)} />
    </div>
  );
}

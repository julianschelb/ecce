import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useOutletContext } from "react-router-dom";
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
  const [menu, setMenu] = useState(false); // phone menu
  const location = useLocation();
  useEffect(() => setMenu(false), [location.pathname]);
  const link = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-2.5 py-1 text-[13px] font-medium transition-colors ${isActive ? "bg-pop-soft text-ink" : "text-ink-2 hover:bg-line-soft hover:text-ink"}`;
  return (
    <div className="flex min-h-screen flex-col">
      <header className="relative border-b border-line bg-gradient-to-b from-bg to-[#f2f1ec]">
        <div className="mx-auto flex h-12 max-w-[1600px] items-center justify-between px-4">
          <NavLink to="/" className="flex items-baseline gap-2">
            <span className="font-serif text-[19px] font-semibold tracking-tight text-ink">ECCE</span>
            <span className="hidden font-mono text-[11px] uppercase tracking-wider text-muted sm:inline">Entity-centric corpus exploration</span>
          </NavLink>
          <button type="button" className="btn btn-sm md:hidden" onClick={() => setMenu((open) => !open)} aria-expanded={menu} aria-controls="site-menu">
            {menu ? "Close" : "Menu"}
          </button>
          <nav id="site-menu" className={`site-nav ${menu ? "is-open" : ""}`}>
            <NavLink to="/" end className={link}>
              Gallery
            </NavLink>
            <a href="/api/docs" className="rounded-md px-2.5 py-1 text-[13px] font-medium text-ink-2 hover:bg-line-soft hover:text-ink" target="_blank" rel="noreferrer">
              API
            </a>
            <button
              type="button"
              className="rounded-md px-2.5 py-1 text-left text-[13px] font-medium text-ink-2 hover:bg-line-soft hover:text-ink"
              onClick={() => {
                setMenu(false);
                setAbout(true);
              }}
            >
              About
            </button>
            <NavLink to="/admin" className={link} title="Administration">
              {isAdmin ? "Admin ●" : "Admin"}
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
